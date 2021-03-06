# This Python file uses the following encoding: utf-8
# -*- coding: utf-8 -*-
import os
import ConfigParser
import threading
import imp
import codecs
import sys
import logging

log = logging.getLogger('messaging')


class Message(threading.Thread):
    def __init__(self, queue):
        super(self.__class__, self).__init__()
        # Creating dict for dynamic modules
        self.modules = []
        self.daemon = True
        self.msg_counter = 0
        self.queue = queue
        self.module_tag = "modules.messaging"

    def load_modules(self, config_dict):
        log.info("Loading configuration file for messaging")
        modules_list = {}

        conf_file = os.path.join(config_dict['conf_folder'], "messaging.cfg")
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read(conf_file)
        # Dynamically loading the modules from cfg.
        if config.items("messaging") > 0:
            for module in config.items("messaging"):
                log.info("Loading %s" % module[0])
                # We load the module, and then we initalize it.
                # When writing your modules you should have class with the
                #  same name as module name
                join_path = [config_dict['root_folder']] + self.module_tag.split('.') + ['{0}.py'.format(module[0])]
                file_path = os.path.join(*join_path)

                tmp = imp.load_source(module[0], file_path)
                class_init = getattr(tmp, module[0])
                class_module = class_init(config_dict['conf_folder'])
                self.modules.append(class_module)
                modules_list[module[0]] = class_module.conf_params
                modules_list[module[0]]['class'] = class_module
        return modules_list

    def msg_process(self, message):
        if ('to' in message) and (message['to'] is not None):
            message['text'] = ', '.join([message['to'], message['text']])

        if 'id' not in message:
            message['id'] = self.msg_counter
            self.msg_counter += 1
        # When we receive message we pass it via all loaded modules
        # All modules should return the message with modified/not modified
        #  content so it can be passed to new module, or to pass to CLI

        for module in self.modules:
            message = module.get_message(message, self.queue)
            try:
                pass
            except Exception as exc:
                log.error(exc)

    def run(self):
        while True:
            self.msg_process(self.queue.get())
