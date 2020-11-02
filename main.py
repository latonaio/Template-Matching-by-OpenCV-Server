#!/usr/bin/env python3
import copy
import math
import os

import aion.common_library as common
from aion.logger_library.LoggerClient import LoggerClient
from aion.websocket_server import BaseServerClass, ServerFunctionFailedException

from template_matching import MultiprocessMatching, OutputImageGenerator

log = LoggerClient("TemplateMatchingServer", stdout_log_level=4)

OUTPUT_PATH = common.get_output_path(os.getcwd(), __file__).replace("-server", "")
N_TEMPLATES = 20
N_PROCESS = 5


class TemplateMatchingServer(BaseServerClass):
    @log.function_log
    async def set_templates(self, sid, data):
        required_keys = ['templates']
        for key in required_keys:
            if key not in data:
                raise ServerFunctionFailedException(f"Bad Request: not found 'templates' in request body")

        templates_data = data['templates']
        self.match.set_templates(templates_data)
        return {}

    @log.function_log
    async def get_matching_result(self, sid, data):
        if self.match.n_process < 1:
            raise ServerFunctionFailedException("there are no templates")

        picture_file_list = data.get("pictureFileList")
        if picture_file_list is None:
            raise ServerFunctionFailedException("there is no picture_file_list in request body")

        for image_path in picture_file_list:
            if not os.path.exists(image_path):
                raise ServerFunctionFailedException(f"Image path {image_path} doesn't exist.")

        data_list = []
        for image_path in picture_file_list:
            results = self.match.run(image_path)

            # Write output image
            self.output_image_generator.request(image_path, results)
            output_path = os.path.join(OUTPUT_PATH, os.path.basename(image_path))

            data_list.append({
                'image_path': image_path,
                'output_path': output_path,
                'results': results
            })

        resp = {'data': data_list}
        return resp

    @classmethod
    def initialize(cls, templates_data, image_path, n_process):
        cls.match = MultiprocessMatching(templates_data, image_path, n_process)
        cls.output_image_generator = OutputImageGenerator(OUTPUT_PATH)

    @classmethod
    def destructor(cls):
        del cls.match
        del cls.output_image_generator


def main():
    try:
        image_path = os.path.join(os.path.dirname(__file__), 'file/data/Example_Full_HD.jpg')

        template_data = {
            "template_image": {
                "path": image_path,
                "trim_points": [[300, 0], [1580, 720]]
            },
            "image": {
                "trim_points": [[400, 100], [1680, 820]],
                "trim_points_ratio": 0.5
            },
            "metadata": {
                "template_id": 1,
                "work_id": 1,
                "pass_threshold": 0.7
            }
        }
        templates_data = []
        for i in range(1, N_TEMPLATES + 1):
            _template_data = copy.deepcopy(template_data)
            _template_data['metadata']['template_id'] = 100 + i
            _template_data['metadata']['work_id'] = 100 + math.ceil(i / (N_TEMPLATES / N_PROCESS))
            templates_data.append(_template_data)

        n_process = N_PROCESS

        TemplateMatchingServer.initialize(templates_data, image_path, n_process)
        TemplateMatchingServer.register_namespace(
            "/template_matching", port=3091)
    finally:
        TemplateMatchingServer.destructor()


if __name__ == "__main__":
    main()
