"""Source-checkout wrapper for the installed anatomy demo.

The composition uses TutorHostRunner, ScriptedTutorDecisionPort, and
OpenAIResponsesTutorDecisionPort in ``study_agent.demo.anatomy``.
"""

from study_agent.demo.anatomy import main, run_reference_demo

__all__ = ["main", "run_reference_demo"]


if __name__ == "__main__":
    main()
