#!/usr/bin/python
  
# Copyright: (c) 2019, Johnathan Kupferer <jkupfere@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.plugins.action import ActionBase
from copy import deepcopy

class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        k8s_api = self._task.args.get('api', {})
        k8s_module_args = dict((k, v) for k, v in self._task.args.items() if k != 'api')
        k8s_module_args.update(k8s_api)

        register = k8s_module_args.pop('register', '')

        result.update(
            self._execute_module(
                module_name='kubernetes.core.k8s_info',
                module_args=k8s_module_args,
                task_vars=task_vars,
            )
        )

        if register:
            result['ansible_facts'] = {
                register: deepcopy(result)
            }
            result['_ansible_facts_cacheable'] = False

        return result
