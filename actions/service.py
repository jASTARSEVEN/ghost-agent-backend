# actions/service.py
from sqlalchemy import text
from actions.db import engine
from actions.schemas import RefundRequest
import asyncio
from datetime import datetime
from chat.socket import room_manager

async def process_refund_request(data, csr_id: int):
    try:
        with engine.connect() as conn:
            with conn.begin():
                # 1. Get the order_id
                result = conn.execute(
                    text("SELECT id FROM orders WHERE order_number = :order_number"),
                    {"order_number": data.order_number}
                ).fetchone()

                if not result:
                    return {"status": "error", "message": "Order not found"}

                order_id = str(result[0])

                # 2. Insert into order_returns table
                conn.execute(
                    text("""
                        INSERT INTO order_returns
                        (order_id, user_id, return_reason, return_status, return_type,
                         refund_amount, requested_date, created_at, updated_at)
                        VALUES
                        (:order_id, :user_id, :reason, 'requested', 'refund', :amount, NOW(), NOW(), NOW())
                    """),
                    {
                        "order_id": order_id,
                        "user_id": str(data.user_id),
                        "reason": data.auto_reason,
                        "amount": float(data.amount)
                    }
                )

                # 3. Update the payment record
                conn.execute(
                    text("""
                        UPDATE payments
                        SET refund_status = 'requested',
                            refund_amount = :amount,
                            refund_reason = :reason,
                            refund_date = NOW()
                        WHERE order_id = :order_id
                    """),
                    {
                        "amount": float(data.amount),
                        "reason": data.auto_reason,
                        "order_id": order_id
                    }
                )

        contextual_update = {
            "event_type" : "user_contextual_message",
            "text" : (
                f"CSR ACTION : REFUND ACCEPT Refund of {data.currency} {data.amount:.2f} "
                f"initiated for Order {data.order_number}"
            ),
            "timestamp" : datetime.utcnow().isoformat() + "Z"
        }

        print(f"Broadcasting refund accept context update to CSR ID:{csr_id}")
        await room_manager.broadcast(str(csr_id), contextual_update)
        
        return {
            "status": "success",
            "order_number": data.order_number,
            "message": f"Refund of {data.currency} {data.amount:.2f} initiated successfully."
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

async def deny_refund_request(data, csr_id: int):
    try:
        with engine.connect() as conn:
            with conn.begin():
                # 1. Get the order_id from the orders table
                result = conn.execute(
                    text("SELECT id FROM orders WHERE order_number = :order_number"),
                    {"order_number": data.order_number}
                ).fetchone()

                if not result:
                    return {"status": "error", "message": "Order not found"}

                order_id = str(result[0])

                # 2. Insert a record in order_returns table (✅ no ::uuid here)
                conn.execute(
                    text("""
                        INSERT INTO order_returns
                        (order_id, user_id, return_reason, return_status, return_type,
                         requested_date, created_at, updated_at)
                        VALUES
                        (:order_id, :user_id, :reason, 'rejected', 'refund', NOW(), NOW(), NOW())
                    """),
                    {
                        "order_id": order_id,
                        "user_id": str(data.user_id),
                        "reason": data.policy_notes or "Refund denied as per policy"
                    }
                )

                # 3. (Optional) update payment refund status
                conn.execute(
                    text("""
                        UPDATE payments
                        SET refund_status = 'denied',
                            refund_reason = :reason,
                            updated_at = NOW()
                        WHERE order_id = :order_id
                    """),
                    {
                        "reason": data.policy_notes or "Refund denied as per policy",
                        "order_id": order_id
                    }
                )
        
        contextual_update = {
            "event_type" : "user_contextual_message",
            "text" : (
                f"CSR ACTION : REFUND DENY Refund denied for order {data.order_number}. "
                f"Reason: {data.policy_notes or 'Refund outside policy guidelines.'}"
            ),
            "timestamp" : datetime.utcnow().isoformat() + "Z"
        }

        asyncio.create_task(
            room_manager.broadcast(str(csr_id), contextual_update))

        return {
            "status": "success",
            "order_number": data.order_number,
            "message": f"Refund denied for order {data.order_number}."
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}