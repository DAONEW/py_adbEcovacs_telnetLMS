import queue
import threading


class CommandQueue:
    """Serializes UI-related tasks to avoid concurrent device actions."""

    def __init__(self):
        self.command_queue = queue.Queue()

    def queue_task(self, func, *args, **kwargs):
        def _task():
            func(*args, **kwargs)

        self.command_queue.put(_task)

    def start_worker(self):
        def worker():
            while True:
                task = self.command_queue.get()
                try:
                    if callable(task):
                        task()
                except Exception as exc:  # pragma: no cover
                    print("Error:", exc)
                finally:
                    self.command_queue.task_done()

        threading.Thread(target=worker, daemon=True).start()
