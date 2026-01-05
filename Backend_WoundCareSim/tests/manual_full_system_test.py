import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.core.coordinator import Coordinator
from app.services.evaluation_service import EvaluationService
from app.services.session_manager import SessionManager

from app.agents.communication_agent import CommunicationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.clinical_agent import ClinicalAgent


LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


async def run_full_system_test():
    """
    Manual end-to-end sanity test for Week-1 → Week-6.
    Includes:
    - Firestore scenario loading
    - Vector Store RAG
    - Real evaluator agents
    - MCQ validation
    - Retry loops
    - Max-retry locking
    - Safety blocking
    - Dressing step
    - JSON log dumping
    """

    scenario_id = "week6_mock_scenario"
    student_id = "manual_test_student"

    log = {
        "scenario_id": scenario_id,
        "student_id": student_id,
        "started_at": datetime.utcnow().isoformat(),
        "steps": []
    }

    print("\n================================================")
    print(" FULL SYSTEM MANUAL TEST (Week-1 → Week-6)")
    print("================================================\n")

    # -------------------------------------------------
    # Core services
    # -------------------------------------------------
    session_manager = SessionManager()
    coordinator = Coordinator()
    evaluation_service = EvaluationService(
        coordinator=coordinator,
        session_manager=session_manager
    )

    # -------------------------------------------------
    # Create session
    # -------------------------------------------------
    session_id = session_manager.create_session(
        scenario_id=scenario_id,
        student_id=student_id
    )

    print(f"[SESSION CREATED] {session_id}")

    agents = [
        CommunicationAgent(),
        KnowledgeAgent(),
        ClinicalAgent()
    ]

    # =================================================
    # HISTORY (success)
    # =================================================
    await run_step(
        step="HISTORY",
        transcript=(
            "Hello, I am a nursing student. "
            "May I confirm your identity, ask about allergies, "
            "and explain the wound care procedure?"
        ),
        evaluation_service=evaluation_service,
        session_manager=session_manager,
        agents=agents,
        log=log,
        auto_advance=True
    )

    # =================================================
    # ASSESSMENT (max-retry lock demonstration)
    # =================================================
    await run_assessment_with_max_retry(
        evaluation_service,
        session_manager,
        agents,
        log
    )

    # =================================================
    # CLEANING (safety violation)
    # =================================================
    await run_step(
        step="CLEANING",
        transcript="I will clean the wound now without washing my hands.",
        evaluation_service=evaluation_service,
        session_manager=session_manager,
        agents=agents,
        log=log,
        expect_safety_block=True
    )

    # =================================================
    # DRESSING (only if not locked — demonstration)
    # =================================================
    session = session_manager.get_session(session_id)
    if not session.get("locked_step"):
        await run_step(
            step="DRESSING",
            transcript="I will apply a sterile dressing and secure it properly.",
            evaluation_service=evaluation_service,
            session_manager=session_manager,
            agents=agents,
            log=log,
            auto_advance=True
        )

    # -------------------------------------------------
    # Dump JSON log
    # -------------------------------------------------
    log["finished_at"] = datetime.utcnow().isoformat()
    log_path = LOG_DIR / f"manual_test_{session_id}.json"

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    print("\n================================================")
    print(" MANUAL FULL-SYSTEM TEST COMPLETE")
    print(f" JSON LOG SAVED → {log_path}")
    print("================================================\n")


# -------------------------------------------------
# Helper functions
# -------------------------------------------------

async def run_step(
    step,
    transcript,
    evaluation_service,
    session_manager,
    agents,
    log,
    auto_advance=False,
    expect_safety_block=False
):
    print(f"\n================ {step} =================")
    print(f"[TRANSCRIPT] {transcript}")

    context = await evaluation_service.prepare_agent_context(
        transcript=transcript,
        scenario_id=log["scenario_id"],
        step=step
    )

    evaluator_outputs = []

    for agent in agents:
        result = await agent.evaluate(
            current_step=step,
            student_input=context["transcript"],
            scenario_metadata=context["scenario_metadata"],
            rag_response=context["rag_context"]
        )
        evaluator_outputs.append(result)
        print(f"{agent.__class__.__name__}: {result.verdict} ({result.confidence})")

    aggregated = await evaluation_service.aggregate_evaluations(
        session_id=session_manager.sessions.keys().__iter__().__next__(),
        evaluator_outputs=evaluator_outputs
    )

    decision = aggregated["decision"]

    log["steps"].append({
        "step": step,
        "transcript": transcript,
        "decision": decision,
        "scores": aggregated.get("scores"),
        "timestamp": datetime.utcnow().isoformat()
    })

    print("[DECISION]", decision)

    if decision["safety_blocked"]:
        print("!!! SAFETY VIOLATION DETECTED !!!")
        session_manager.lock_current_step(
            session_manager.sessions.keys().__iter__().__next__()
        )

    elif auto_advance and decision["ready_for_next_step"]:
        next_step = session_manager.advance_step(
            session_manager.sessions.keys().__iter__().__next__()
        )
        print(f"[ADVANCED TO] {next_step}")


async def run_assessment_with_max_retry(
    evaluation_service,
    session_manager,
    agents,
    log
):
    print("\n================ ASSESSMENT (MAX RETRY) =================")

    transcript = "The wound looks fine. I will continue."
    wrong_mcq = {"q1": "Remove dressing", "q2": "Dry dressing"}

    for attempt in range(1, 5):
        print(f"\n[ATTEMPT {attempt}]")

        context = await evaluation_service.prepare_agent_context(
            transcript=transcript,
            scenario_id=log["scenario_id"],
            step="ASSESSMENT"
        )

        evaluator_outputs = []

        for agent in agents:
            result = await agent.evaluate(
                current_step="ASSESSMENT",
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
            evaluator_outputs.append(result)
            print(f"{agent.__class__.__name__}: {result.verdict}")

        aggregated = await evaluation_service.aggregate_evaluations(
            session_id=session_manager.sessions.keys().__iter__().__next__(),
            evaluator_outputs=evaluator_outputs,
            student_mcq_answers=wrong_mcq
        )

        decision = aggregated["decision"]

        log["steps"].append({
            "step": "ASSESSMENT",
            "attempt": attempt,
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat()
        })

        print("[DECISION]", decision)

        if decision["ready_for_next_step"]:
            session_manager.advance_step(
                session_manager.sessions.keys().__iter__().__next__()
            )
            print("[ADVANCED]")
            return

        session_manager.increment_attempt(
            session_manager.sessions.keys().__iter__().__next__()
        )

        if session_manager.get_session(
            session_manager.sessions.keys().__iter__().__next__()
        ).get("locked_step"):
            print("!!! MAX RETRIES REACHED → SESSION LOCKED !!!")
            return


# -------------------------------------------------
# Entry point
# -------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_full_system_test())
