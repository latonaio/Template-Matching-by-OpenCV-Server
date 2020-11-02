import sys
import more_itertools
import multiprocessing
import traceback

from template_matching.core.matcher import Matcher
from template_matching.errors import TemplateMatchingException
from aion.logger_library.LoggerClient import LoggerClient

log = LoggerClient("TemplateMatchingServer")


def pool_matching(args_queue, return_queue, templates_data, image_path):
    matcher = Matcher(templates_data, image_path)

    while True:
        exit_status = True
        return_value = None

        function_name, kwargs = args_queue.get()

        try:
            if function_name == 'set_templates':
                matcher.set_templates(kwargs['templates_data'])

            elif function_name == 'run':
                return_value = matcher.run(kwargs['image_path'])

            else:
                raise TemplateMatchingException('pool_matching() recieve Invalid function name ({function_name}).')

        except Exception:
            exit_status = False
            log.print(traceback.format_exc())

        return_queue.put((exit_status, return_value))
    return


class MatchingProcess():
    def __init__(self, templates_data, image_path):
        ctx = multiprocessing.get_context('spawn')
        self.args_queue = ctx.Queue()
        self.return_queue = ctx.Queue()
        self.process = ctx.Process(target=pool_matching, args=(self.args_queue, self.return_queue, templates_data, image_path))
        self.process.start()

    def __del__(self):
        self.terminate()

    def terminate(self):
        if hasattr(self, 'process'):
            self.process.terminate()
        return

    def start_set_templates(self, templates_data):
        self.args_queue.put(('set_templates', {'templates_data': templates_data}))
        return

    def start_template_matching(self, image_path):
        self.args_queue.put(('run', {'image_path': image_path}))
        return

    def get_from_return_queue(self):
        exit_status, return_value = self.return_queue.get()
        return exit_status, return_value


class MultiprocessMatching():
    def __init__(self, templates_data, image_path, n_process=8):
        assert len(templates_data) > n_process

        self.n_process = n_process
        self.processes = []

        divided_templates_data = [list(x) for x in more_itertools.divide(self.n_process, templates_data)]

        for _templates_data in divided_templates_data:
            process = MatchingProcess(_templates_data, image_path)
            process.is_active = True
            self.processes.append(process)

    def __del__(self):
        self.terminate_all()

    def terminate_all(self):
        for process in self.processes:
            process.terminate()
        return

    def set_templates(self, templates_data):
        divided_templates_data = [list(x) for x in more_itertools.divide(self.n_process, templates_data)]

        for process, _templates_data in zip(self.processes, divided_templates_data):
            if _templates_data:
                process.start_set_templates(_templates_data)
                process.is_active = True
            else:
                process.is_active = False

        for process in self.processes:
            if process.is_active:
                exit_status, _ = process.get_from_return_queue()
                if not exit_status:
                    self.terminate_all()
                    log.print('MultiprocessMatching.set_templates() is faild. Kill all child processes and system exit.')
                    sys.exit(1)

        return

    def run(self, image_path):
        for process in self.processes:
            if process.is_active:
                process.start_template_matching(image_path)

        results = []
        for process in self.processes:
            if process.is_active:
                exit_status, _results = process.get_from_return_queue()
                if not exit_status:
                    self.terminate_all()
                    log.print('MultiprocessMatching.get_matching_result() is faild. Kill all child processes and system eixt.')
                    sys.exit(1)
                results.extend(_results)

        return results


if __name__ == "__main__":
    import time
    from pprint import pprint

    templates_data = {
        "template_image": {
            "path": "file/data/Example_Full_HD.jpg",
            "trim_points": [[400, 100], [1680, 820]]
        },
        "image": {
            "trim_points": [[390, 90], [1690, 830]],
            "trim_points_ratio": 0.5
        },
        "metadata": {
            "template_id": 1,
            "work_id": 1
        }
    }
    templates_data = [templates_data] * 15

    image_path = "file/data/Example_Full_HD.jpg"

    mather = MultiprocessMatching(templates_data, image_path, n_process=5)
    mather.set_templates(templates_data)

    # run() のみの時間を測るので、set_templates()が完全に終わるのを待つ
    time.sleep(2)

    s = time.time()
    matching_data = mather.run(image_path)
    e = time.time()
    pprint(matching_data)
    print(e - s)
    del mather
