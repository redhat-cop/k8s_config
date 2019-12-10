#!/usr/bin/python
  
# Copyright: (c) 2019, Johnathan Kupferer <jkupfere@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.errors import AnsibleError, AnsibleUndefinedVariable
from ansible.plugins.action import ActionBase

class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        git_module_args = self._task.args.get('module_args')
        git_module_args['dest'] = self._task.args.get('dest')

        result.update(
            self._execute_module(
                module_name='git',
                module_args=git_module_args,
                task_vars=task_vars,
            )
        )
        return result
