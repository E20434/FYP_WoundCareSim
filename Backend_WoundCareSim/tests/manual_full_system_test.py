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


# -------------------------------------------------
# Logging setup
# -------------------------------------------------
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


async def run_full_system_test():
    """
    Manual end-to-end system validation (Week-1 → Week-6).

    EDUCATIONAL MODE:
    - No blocking
    - No retries
    - No safety locks
    - Student can always continue
    - Feedback is given AFTER each step
    """

    scenario_id = "week6_mock_scenario"
    student_id = "manual_test_student"

    print("\n================================================")
    print(" FULL SYSTEM MANUAL TEST (Week-1 → Week-6)")
    print("================================================\n")

    log = {
        "scenario_id": scenario_id,
        "student_id": student_id,
        "started_at": datetime.utcnow().isoformat(),
        "steps": []
    }

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
    # PROCEDURE STEPS
    # =================================================
    await run_step(
        step="HISTORY",
        transcript=(
            "Hello, I am a nursing student. "
            "May I confirm your identity, ask about allergies, "
            "and explain the wound care procedure?"
        ),
        evaluation_service=evaluation_service,
        session_id=session_id,
        agents=agents,
        log=log
    )

    await run_assessment(
        evaluation_service=evaluation_service,
        session_id=session_id,
        agents=agents,
        log=log
    )

    await run_step(
        step="CLEANING",
        transcript="I will clean the wound now without washing my hands.",
        evaluation_service=evaluation_service,
        session_id=session_id,
        agents=agents,
        log=log
    )

    await run_step(
        step="DRESSING",
        transcript="I will apply a sterile dressing and secure it properly.",
        evaluation_service=evaluation_service,
        session_id=session_id,
        agents=agents,
        log=log
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
    session_id,
    agents,
    log
):
    print(f"\n================ {step} =================")
    print(f"[STUDENT INPUT] {transcript}")

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
        print(f"{result.agent_name}: {result.verdict} ({result.confidence})")

    aggregated = await evaluation_service.aggregate_evaluations(
        session_id=session_id,
        evaluator_outputs=evaluator_outputs
    )

    # -----------------------------
    # Safe decision handling
    # -----------------------------
    decision = aggregated.get("decision", {})

    print("\n--- FEEDBACK SUMMARY ---")
    for s in aggregated.get("summary", {}).get("strengths", []):
        print("✔", s)

    for i in aggregated.get("summary", {}).get("issues_detected", []):
        print("✖", i)

    print("\n[SCORES]", aggregated.get("scores"))
    print("[READINESS]", decision.get("ready_for_next_step", "N/A"))

    log["steps"].append({
        "step": step,
        "transcript": transcript,
        "summary": aggregated.get("summary"),
        "scores": aggregated.get("scores"),
        "decision": decision,
        "timestamp": datetime.utcnow().isoformat()
    })


async def run_assessment(
    evaluation_service,
    session_id,
    agents,
    log
):
    print("\n================ ASSESSMENT =================")

    transcript = "The wound looks fine. I will continue."
    student_mcq_answers = {
        "q1": "Remove dressing",
        "q2": "Dry dressing"
    }

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
        print(f"{result.agent_name}: {result.verdict}")

    aggregated = await evaluation_service.aggregate_evaluations(
        session_id=session_id,
        evaluator_outputs=evaluator_outputs,
        student_mcq_answers=student_mcq_answers
    )

    print("\n--- MCQ FEEDBACK ---")
    print(aggregated.get("mcq_result", "No MCQ feedback"))

    log["steps"].append({
        "step": "ASSESSMENT",
        "transcript": transcript,
        "mcq_answers": student_mcq_answers,
        "mcq_result": aggregated.get("mcq_result"),
        "decision": aggregated.get("decision", {}),
        "timestamp": datetime.utcnow().isoformat()
    })


# -------------------------------------------------
# Entry point
# -------------------------------------------------
if __name__ == "__main__":
    asyncio.run(run_full_system_test())
