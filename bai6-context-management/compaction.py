"""B1: CompactionMiddleware, nén working context theo pipeline slide 26.

    Observe token budget → Prune tool output → Build checkpoint → Reinject → Resume & validate

Tự viết thay vì dùng langchain SummarizationMiddleware có sẵn, vì bản có sẵn chỉ tóm tắt tự do (4 mục chung chung);
đề và slide (tr. 20-23) yêu cầu structured checkpoint đủ 7 trường + selective keep/drop. Từ bản có sẵn chỉ học cách
thay messages (RemoveMessage(REMOVE_ALL_MESSAGES) + danh sách mới) và cách chọn điểm cắt để không làm mồ côi ToolMessage.
"""

from __future__ import annotations

import logging
import uuid

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from pydantic import BaseModel, Field

import paths
from config import COMPACT_KEEP_LAST_MESSAGES, COMPACT_TRIGGER_TOKENS, PRUNE_MIN_CHARS
from pruning import PRUNED_MARKER, archive_raw, prune_tool_output

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4  # ước lượng thô khi không có usage thật
CHECKPOINT_MARKER = "[CHECKPOINT]"


class Checkpoint(BaseModel):
    """Structured checkpoint (slide 22): đủ thông tin để agent làm tiếp, không phải bản recap của chat."""

    # Mọi trường có giá trị mặc định rỗng: model bỏ sót một trường thì vẫn dựng được checkpoint, và missing_fields() báo trường đó
    # (thay vì ném ValidationError làm chết cả phiên).
    goal: str = Field(default="", description="Mục tiêu tổng của phiên làm việc, một hai câu.")
    current_state: str = Field(default="", description="Đang ở đâu tại ĐIỂM CUỐI của lịch sử được đưa: đã làm tới bước nào, kết quả mới nhất là gì.")
    constraints: list[str] = Field(default_factory=list, description="CHỈ những điều CHÍNH NGƯỜI DÙNG đã yêu cầu bắt buộc hoặc cấm, giữ nguyên ý, kể cả ở checkpoint cũ. Không ghi việc trợ lý đã làm hay yêu cầu một lần đang xử lý.")
    findings: list[str] = Field(default_factory=list, description="Bằng chứng/phát hiện đã xác nhận từ log và test (tên lỗi, số lần, nơi xảy ra), ngắn gọn.")
    failed_attempts: list[str] = Field(default_factory=list, description="Mỗi cách đã thử và kết quả của nó, để không thử lại.")
    files: list[str] = Field(default_factory=list, description="Các file/log/file mã nguồn đã đọc hoặc liên quan. Không liệt kê đường dẫn traces/archive.")
    next_action: str = Field(default="", description="Bước tiếp theo hợp lý nhất, cụ thể.")

    def missing_fields(self) -> list[str]:
        """Tên các trường rỗng (validate checkpoint: trường quan trọng không được trống)."""
        return [name for name in type(self).model_fields if not getattr(self, name)]

    def render(self, latest_user_request: str | None = None) -> str:
        """latest_user_request: yêu cầu hiện tại của user nếu nó nằm trong phần bị nén. Ghi NGUYÊN VĂN, không qua LLM diễn đạt lại."""
        def bullets(items: list[str]) -> str:
            return "\n".join(f"- {item}" for item in items) or "- (không có)"

        request_line = f"yêu cầu hiện tại của user (nguyên văn): {latest_user_request}\n" if latest_user_request else ""
        return (
            f"{CHECKPOINT_MARKER} Trạng thái đã nén của phần hội thoại cũ (thay cho các message đã bị bỏ). Coi đây là nguồn sự thật. "
            "Các message đứng ngay sau checkpoint là phần gần nhất, giữ nguyên và MỚI HƠN checkpoint: nếu lệch nhau thì theo các message đó.\n"
            f"goal: {self.goal}\n"
            f"current_state: {self.current_state}\n"
            f"{request_line}"
            f"constraints:\n{bullets(self.constraints)}\n"
            f"findings:\n{bullets(self.findings)}\n"
            f"failed_attempts:\n{bullets(self.failed_attempts)}\n"
            f"files: {', '.join(self.files) or '(không có)'}\n"
            f"next_action: {self.next_action}"
        )


CHECKPOINT_SYSTEM_PROMPT = """Bạn nén lịch sử làm việc của một agent debug thành CHECKPOINT có cấu trúc.
Checkpoint KHÔNG phải bản kể lại cuộc trò chuyện: mục tiêu là đủ thông tin để agent làm tiếp ĐÚNG việc mà không cần đọc lại lịch sử.

Chọn lọc:
- GIỮ: quyết định, lỗi chưa giải quyết, yêu cầu bắt buộc của người dùng (ghi đủ, đúng ý, kể cả ràng buộc nói ở lượt đầu).
- RÚT GỌN: output dài chỉ giữ dòng lỗi chính, kèm số lần xuất hiện nếu có.
- BỎ: log trùng, chi tiết dữ liệu dễ tái tạo. Nhưng mỗi cách đã thử và kết quả của nó vẫn ghi vào failed_attempts.
- constraints chỉ gồm điều CHÍNH NGƯỜI DÙNG đã yêu cầu bắt buộc hoặc cấm (ví dụ "không đổi API"). Không đưa vào đó việc trợ lý đã làm,
  yêu cầu một lần đang xử lý, hay đề xuất đang chờ duyệt; những thứ đó thuộc current_state hoặc next_action.
- current_state mô tả trạng thái tại điểm CUỐI của lịch sử được đưa; các message sau đó được giữ nguyên bên ngoài checkpoint.
- Nếu lịch sử có [CHECKPOINT] cũ: gộp vào checkpoint mới, không làm mất ràng buộc hay failed_attempts cũ.
- Điền đủ 7 trường; trường nào chưa có gì thì để danh sách rỗng hoặc chuỗi rỗng.
- Chỉ dùng thông tin có trong lịch sử, không bịa."""


# ---------- Hàm thuần (không gọi LLM), có thể test offline ----------

def message_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def _message_chars(message) -> int:
    chars = len(message_text(message))
    for call in getattr(message, "tool_calls", None) or []:
        chars += len(call["name"]) + len(str(call["args"]))
    return chars


def estimate_tokens(messages: list) -> int:
    """Ước lượng thô: ký tự / 4. Chỉ dùng khi chưa có usage thật."""
    return sum(_message_chars(m) for m in messages) // CHARS_PER_TOKEN


def measure_context_tokens(messages: list) -> tuple[int, str]:
    """Quan sát token budget (slide 26 bước 1). Trả (số token, nguồn).

    Ưu tiên usage THẬT của AIMessage gần nhất (input + output của lần gọi đó) cộng ước lượng phần mới thêm sau nó
    (ToolMessage vừa về chưa được model nhìn thấy). Chưa có usage thì ước lượng toàn bộ.
    """
    for i in range(len(messages) - 1, -1, -1):
        message = messages[i]
        usage = getattr(message, "usage_metadata", None)
        if isinstance(message, AIMessage) and usage:
            return usage["input_tokens"] + usage.get("output_tokens", 0) + estimate_tokens(messages[i + 1:]), "usage"
    return estimate_tokens(messages), "ước lượng"


def find_cutoff(messages: list, keep_last: int) -> int:
    """Điểm cắt: messages[:cutoff] bị nén, messages[cutoff:] giữ lại.

    Bẫy: đuôi giữ lại không được bắt đầu bằng ToolMessage mồ côi (API báo lỗi nếu ToolMessage không có
    AIMessage.tool_calls tương ứng đứng trước). Nên từ vị trí mục tiêu lùi về trước tới khi gặp message không phải
    ToolMessage: đó là Human hoặc AI (kèm tool_calls) và các ToolMessage của nó nằm trọn trong đuôi.
    """
    cutoff = len(messages) - keep_last
    while cutoff > 0 and isinstance(messages[cutoff], ToolMessage):
        cutoff -= 1
    return max(cutoff, 0)


def orphan_tool_messages(messages: list) -> list[str]:
    """tool_call_id của các ToolMessage không có AIMessage.tool_calls tương ứng đứng trước trong danh sách."""
    seen_call_ids: set[str] = set()
    orphans = []
    for message in messages:
        if isinstance(message, AIMessage):
            seen_call_ids.update(call["id"] for call in message.tool_calls if call.get("id"))
        elif isinstance(message, ToolMessage) and message.tool_call_id not in seen_call_ids:
            orphans.append(message.tool_call_id)
    return orphans


def _is_checkpoint(message) -> bool:
    return isinstance(message, HumanMessage) and bool(message.additional_kwargs.get("compacted"))


def _without_usage(messages: list) -> list:
    """Bỏ usage_metadata cũ của các AIMessage (số đo của lần gọi trước khi nén, không còn đúng)."""
    return [m.model_copy(update={"usage_metadata": None}) if isinstance(m, AIMessage) else m for m in messages]


def render_for_checkpoint(messages: list) -> str:
    """Dựng lịch sử (đã prune) thành text cho LLM tạo checkpoint."""
    parts = []
    for m in messages:
        if _is_checkpoint(m):
            parts.append(f"[CHECKPOINT CŨ]\n{message_text(m)}")
        elif isinstance(m, HumanMessage):
            parts.append(f"[USER] {message_text(m)}")
        elif isinstance(m, AIMessage):
            parts += [f"[ASSISTANT gọi tool] {c['name']}({c['args']})" for c in m.tool_calls]
            if message_text(m).strip():
                parts.append(f"[ASSISTANT] {message_text(m)}")
        elif isinstance(m, ToolMessage):
            parts.append(f"[TOOL {m.name}] {message_text(m)[:4000]}")
    return "\n".join(parts)


# ---------- Middleware ----------

class CompactionMiddleware(AgentMiddleware):
    """Trước mỗi lần gọi model: nếu context vượt ngưỡng thì prune + checkpoint + thay messages."""

    def __init__(
        self,
        model,
        *,
        trigger_tokens: int = COMPACT_TRIGGER_TOKENS,
        keep_last_messages: int = COMPACT_KEEP_LAST_MESSAGES,
        prune_min_chars: int = PRUNE_MIN_CHARS,
        token_logger=None,
    ) -> None:
        super().__init__()
        self.trigger_tokens = trigger_tokens
        self.keep_last_messages = keep_last_messages
        self.prune_min_chars = prune_min_chars
        self.token_logger = token_logger
        self.events: list[dict] = []  # mỗi lần compact một dict, demo dùng để in bảng và tự kiểm
        self._structured_model = model.with_structured_output(Checkpoint, method="function_calling")

    def before_model(self, state: AgentState, runtime) -> dict | None:
        messages = list(state["messages"])
        for message in messages:
            if message.id is None:
                message.id = str(uuid.uuid4())

        tokens_before, source = measure_context_tokens(messages)
        if tokens_before < self.trigger_tokens:
            return None

        cutoff = find_cutoff(messages, self.keep_last_messages)
        head, tail = messages[:cutoff], messages[cutoff:]
        if orphans := orphan_tool_messages(tail):
            logger.warning("Không compact: đuôi giữ lại có ToolMessage mồ côi %s", orphans)
            return None

        archived: list[str] = []
        tail = [self._prune(m, archived) for m in tail]
        if all(_is_checkpoint(m) for m in head):
            # Đầu rỗng hoặc chỉ còn checkpoint cũ: không có gì mới để nén, chỉ rút gọn tool output ở đuôi cho context nhỏ lại.
            if not archived:
                return None
            print(f"\n=== PRUNED (chưa cần checkpoint mới): đo {tokens_before:,} token ({source}); rút gọn {len(archived)} tool output, archive: {archived} ===\n")
            return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *head, *_without_usage(tail)]}

        # Yêu cầu hiện tại của user mà nằm trong phần bị nén thì ghi nguyên văn vào checkpoint, không để LLM diễn đạt lại.
        latest_request = None
        if not any(isinstance(m, HumanMessage) for m in tail):
            latest_request = next((message_text(m) for m in reversed(head) if isinstance(m, HumanMessage) and not _is_checkpoint(m)), None)
        head = [self._prune(m, archived) for m in head]
        checkpoint = self._build_checkpoint(head)
        missing = checkpoint.missing_fields()

        # Message đuôi giữ lại mang usage của lần gọi TRƯỚC khi nén, không còn đúng nữa: bỏ đi để lần đo sau không đọc nhầm.
        tail = _without_usage(tail)
        checkpoint_message = HumanMessage(content=checkpoint.render(latest_request), additional_kwargs={"compacted": True})
        new_messages = [checkpoint_message, *tail]

        tokens_after = estimate_tokens(new_messages)
        self.events.append({
            "tokens_before": tokens_before, "before_source": source, "tokens_after_estimate": tokens_after,
            "messages_before": len(messages), "messages_after": len(new_messages),
            "archived": archived, "missing_fields": missing, "checkpoint": checkpoint.model_dump(),
        })
        self._announce(self.events[-1], checkpoint_message)
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *new_messages]}

    def _prune(self, message, archived: list[str]):
        """ToolMessage dài → bản rút gọn (raw ghi vào archive). Message khác, hoặc ToolMessage ngắn: giữ nguyên."""
        if not isinstance(message, ToolMessage):
            return message
        text = message_text(message)
        if len(text) <= self.prune_min_chars or text.startswith(PRUNED_MARKER):
            return message
        path = archive_raw(message.tool_call_id or message.id, text)
        ref = path.relative_to(paths.PROJECT_ROOT).as_posix()
        archived.append(ref)
        return ToolMessage(content=prune_tool_output(text, ref), tool_call_id=message.tool_call_id, name=message.name, id=message.id)

    def _build_checkpoint(self, head: list) -> Checkpoint:
        request = [SystemMessage(CHECKPOINT_SYSTEM_PROMPT), HumanMessage(f"Lịch sử cần nén:\n{render_for_checkpoint(head)}")]
        config = {"tags": ["checkpoint"]}
        if self.token_logger is not None:
            config["callbacks"] = [self.token_logger]
        for attempt in (1, 2):
            try:
                result = self._structured_model.invoke(request, config=config)
            except Exception as exc:  # model không gọi tool, hoặc args sai định dạng (OutputParserException, ValidationError)
                logger.warning("Lần %d: lỗi khi tạo checkpoint (%s: %s)", attempt, type(exc).__name__, str(exc)[:200])
                continue
            if isinstance(result, Checkpoint):
                return result
            logger.warning("Lần %d: model không trả checkpoint hợp lệ (%r)", attempt, result)
        raise RuntimeError("Không tạo được checkpoint sau 2 lần thử; dừng thay vì bịa tóm tắt.")

    @staticmethod
    def _announce(event: dict, checkpoint_message) -> None:
        print(f"\n=== COMPACTED: {event['tokens_before']:,} → {event['tokens_after_estimate']:,} tokens "
              f"(trước: {event['before_source']}; sau: ước lượng ký tự/4, chưa tính system prompt và tool schema) ===")
        print(f"messages {event['messages_before']} → {event['messages_after']}; tool output đã archive: {event['archived'] or 'không có'}")
        if event["missing_fields"]:
            print(f"CẢNH BÁO: checkpoint thiếu trường {event['missing_fields']}")
        print(message_text(checkpoint_message))
        print("=== hết checkpoint ===\n")
