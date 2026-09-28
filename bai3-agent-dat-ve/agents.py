# -*- coding: utf-8 -*-
"""BTVN#3 · Ba mẫu thiết kế agent. Cùng model, cùng tool, cùng harness;
chỉ khác cách tổ chức suy luận.

    chay_react         ReAct: suy luận → gọi tool → quan sát → lặp tới khi thôi gọi tool
    chay_plan_execute  Plan-then-Execute: lập trọn kế hoạch một lần, thực thi tuần tự, không lập lại
    chay_lai           Lai: lập todo, làm, cập nhật lại kế hoạch theo observation (TodoListMiddleware)
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field

import tools_mock
from harness import HarnessMiddleware, YeuCau, cau_hoi_khach, ket_thuc, system_prompt

GIOI_HAN_DE_QUY = 80        # trần cứng của LangGraph, lớp bảo vệ cuối cùng


def tao_model():
    """DeepSeek qua API tương thích OpenAI, dùng cùng biến môi trường với bài 2."""
    load_dotenv(Path(__file__).with_name(".env"))
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key or key.startswith("your_"):
        raise SystemExit("Thiếu DEEPSEEK_API_KEY. Copy .env.example thành .env rồi điền key.")
    return ChatOpenAI(model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
                      base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                      api_key=key, temperature=0)


def _goi(agent, noi_dung: str, h: HarnessMiddleware) -> str:
    """invoke một agent; nếu chạm trần cứng của LangGraph thì vẫn dừng có bàn giao."""
    try:
        kq = agent.invoke({"messages": [{"role": "user", "content": noi_dung}]},
                          {"recursion_limit": GIOI_HAN_DE_QUY})
        return str(kq["messages"][-1].content)
    except GraphRecursionError:
        h.dung_lai("BAN_GIAO", f"RECURSION · chạm trần cứng {GIOI_HAN_DE_QUY} bước của LangGraph",
                   "Agent chạy quá lâu. Kiểm tra trace để tìm vòng hỏng đầu tiên.")
        return ""


# ================================================================ ReAct
def chay_react(yc: YeuCau, model) -> dict:
    h = HarnessMiddleware(yc)
    agent = create_agent(model, tools_mock.tools_langchain(),
                         system_prompt=system_prompt(yc), middleware=[h])
    tra_loi = _goi(agent, cau_hoi_khach(yc), h)
    return ket_thuc(h, tra_loi)


# ==================================================== Plan-then-Execute
class KeHoach(BaseModel):
    buoc: list[str] = Field(description="Các bước ngắn gọn theo thứ tự, mỗi bước là một việc cụ thể")


def chay_plan_execute(yc: YeuCau, model) -> dict:
    h = HarnessMiddleware(yc)

    # 1 · Lập kế hoạch: một lần gọi model, chưa chạy tool nào.
    planner = model.with_structured_output(KeHoach, method="function_calling", include_raw=True)
    out = planner.invoke([
        ("system", system_prompt(yc) + "\n\nNhiệm vụ lúc này: CHỈ lập kế hoạch (tối đa 6 bước), "
                   "chưa thực hiện. Tool sẵn có: search_flights, check_seat, book_seat, pay, get_booking."),
        ("user", cau_hoi_khach(yc)),
    ])
    h.dem_model(out["raw"])
    ke_hoach = out["parsed"].buoc if out["parsed"] else []
    for i, b in enumerate(ke_hoach, 1):
        h.trace.append(f"[KẾ HOẠCH {i}] {b}")

    # Kế hoạch nhìn thấy trước khi chạy nên harness duyệt được ngay tại đây.
    if not 1 <= len(ke_hoach) <= 8:
        h.dung_lai("BAN_GIAO", f"PLAN · kế hoạch không hợp lệ ({len(ke_hoach)} bước)",
                   "Model không lập được kế hoạch dùng được. Lập kế hoạch thủ công?")
        return ket_thuc(h, "")

    # 2 · Thực thi tuần tự từng bước, không lập lại kế hoạch.
    executor = create_agent(
        model, tools_mock.tools_langchain(),
        system_prompt=system_prompt(yc) + "\n\nBạn là bộ thực thi: chỉ làm đúng MỘT bước được giao, "
                                          "xong thì tóm tắt kết quả (kèm flight_id, seat, booking_code nếu có).",
        middleware=[h])
    ds_buoc = "\n".join(f"{i}. {b}" for i, b in enumerate(ke_hoach, 1))
    da_lam, tra_loi = [], ""
    for i, buoc in enumerate(ke_hoach, 1):
        if h.dung:
            break
        h.trace.append(f"[BƯỚC {i}] {buoc}")
        tra_loi = _goi(executor,
                       f"Yêu cầu gốc: {cau_hoi_khach(yc)}\nKế hoạch:\n{ds_buoc}\n"
                       f"Kết quả các bước trước:\n{chr(10).join(da_lam) or '(chưa có)'}\n\n"
                       f"Bây giờ chỉ thực hiện bước {i}: {buoc}", h)
        da_lam.append(f"Bước {i}: {tra_loi}")
    return ket_thuc(h, tra_loi)


# ============================================================ Lai
def chay_lai(yc: YeuCau, model) -> dict:
    h = HarnessMiddleware(yc)
    agent = create_agent(
        model, tools_mock.tools_langchain(),
        system_prompt=system_prompt(yc) + "\n\nTrước khi làm, dùng write_todos lập kế hoạch các bước. "
                                          "Sau mỗi kết quả làm thay đổi tình hình (hết chỗ, bị từ chối...), "
                                          "cập nhật lại kế hoạch bằng write_todos rồi làm tiếp.",
        middleware=[TodoListMiddleware(), h])
    tra_loi = _goi(agent, cau_hoi_khach(yc), h)
    return ket_thuc(h, tra_loi)


MAU = {"react": chay_react, "plan": chay_plan_execute, "lai": chay_lai}


def chay(mau: str, yc: YeuCau, model) -> dict:
    """Chạy một mẫu trên một yêu cầu, môi trường mock được reset trước mỗi lần."""
    tools_mock.reset()
    t0 = time.perf_counter()
    kq = MAU[mau](yc, model)
    kq["giay"] = round(time.perf_counter() - t0, 1)
    kq["mau"] = mau
    return kq
