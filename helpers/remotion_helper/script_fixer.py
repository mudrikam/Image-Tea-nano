from PySide6.QtCore import QThread, Signal

from helpers.remotion_helper.remotion_refine_agent import RemotionRefineAgent


class ScriptFixWorker(QThread):
    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(self, api_key, endpoint, service, model, script_content, error_msg, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.script_content = script_content
        self.error_msg = error_msg

    def _call_ai(self, prompt):
        from helpers.remotion_helper.remotion_ai_client import call_remotion_ai
        return call_remotion_ai(
            self.api_key, self.endpoint, self.service, self.model, prompt, timeout=45
        )

    def run(self):
        instruction = (
            'Fix the following Remotion runtime or render error. Preserve the intended visual behavior, '
            'make the smallest safe change, and verify the TypeScript/JSX structure.\n\n'
            f'ERROR:\n{self.error_msg}'
        )

        def emit_step(step):
            self.progress.emit(step.message)

        try:
            agent = RemotionRefineAgent(
                self._call_ai,
                self.script_content,
                instruction,
                emit_step=emit_step,
            )
            result = agent.run()
            self.finished.emit(result.success, result.script if result.success else result.message)
        except Exception as exc:
            self.finished.emit(False, str(exc))


__all__ = ['ScriptFixWorker']
