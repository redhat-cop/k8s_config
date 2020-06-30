#!/usr/bin/python
#
# Copyright: (c) 2019, Johnathan Kupferer <jkupfere@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# k8s_git_clone action plugin
#
# This is a wrapper around the git module to facilitate arguments for git being passed in
# a single `module_args` argument.
#

from ansible.errors import AnsibleError, AnsibleUndefinedVariable
from ansible.plugins.action import ActionBase

class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        # git module arugements are passed through module_args
        git_module_args = self._task.args.get('module_args')
        # The destitation is determined by k8s_config at run time
        git_module_args['dest'] = self._task.args.get('dest')

        # Write ssh key to temp file if passed as key_content
        tmp_key_file = None
        if git_module_args.get('key_content'):
            r_tempfile = self._execute_module(
                module_name='tempfile',
                module_args=dict(state='file'),
                task_vars=task_vars,
            )
            tmp_key_file = r_tempfile['path']
            self._execute_module(
                module_name='copy',
                module_args=dict(
                    dest=tmp_key_file,
                    content=git_module_args['key_content'],
                ),
                task_vars=task_vars,
            )
            git_module_args['key_file'] = tmp_key_file
            del git_module_args['key_content']

        result.update(
            self._execute_module(
                module_name='git',
                module_args=git_module_args,
                task_vars=task_vars,
            )
        )

        if tmp_key_file:
            self._execute_module(
                module_name='file',
                module_args=dict(
                    path=tmp_key_file,
                    state='absent',
                ),
                task_vars=task_vars,
            )

        return result
