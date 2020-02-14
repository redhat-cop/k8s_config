#!/usr/bin/python
  
# Copyright: (c) 2019, Johnathan Kupferer <jkupfere@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.plugins.action import ActionBase

class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        output_file = task_vars.get('k8s_config_output_file')
        if output_file:
            raise Exception(output_file)

        k8s_api = self._task.args.get('api', {})
        k8s_module_args = dict((k, v) for k, v in self._task.args.items() if k != 'api')
        k8s_module_args.update(k8s_api)

        result.update(
            self._execute_module(
                module_name='k8s_namespace',
                module_args=k8s_module_args,
                task_vars=task_vars,
            )
        )
        return result
