#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2019, Johnathan Kupferer
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import absolute_import, division, print_function

import sys

try:
    from openshift.dynamic.exceptions import \
        DynamicApiError, NotFoundError, ConflictError, \
        ForbiddenError, KubernetesValidateMissing
except ImportError:
    # Exceptions handled in common
    pass

__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''

module: k8s_namespace

short_description: Manage Kubernetes (K8s) namespaces

version_added: "2.9"

author:
- Johnathan Kupferer

description:
- Use the OpenShift Python client to manage namespaces.

extends_documentation_fragment:
- k8s_auth_options

options:
  name:
    description:
    - Namespace name to create

requirements:
- "python >= 3.7"
- "openshift >= 0.9.2"
- "PyYAML >= 5.1.2"
'''

EXAMPLES = '''
- name: Create a k8s namespace
  k8s_namespace:
    name: test-namespace
'''

RETURN = '''
result:
  description:
  - The created, patched, or otherwise present namespace.
  returned: success
  type: complex
  contains:
    resource:
      description: The patched resource.
      returned: success
      type: complex
    kind:
      description: Represents the REST resource this object represents.
      returned: success
      type: str
    metadata:
      description: Standard object metadata. Includes name, namespace, annotations, labels, etc.
      returned: success
      type: complex
'''

import copy
import traceback

from ansible.module_utils.k8s.common import AUTH_ARG_SPEC
from ansible.module_utils.k8s.raw import KubernetesRawModule

NAMESPACE_ARG_SPEC = {
    'name': {
        'type': 'str',
        'required': True
    },
    # Required by k8s raw module...
    'merge_type': {
        'type': 'list',
        'choices': ['json', 'merge', 'strategic-merge']
    },
}

class KubernetesNamespace(KubernetesRawModule):
    def __init__(self, *args, **kwargs):
        super(KubernetesNamespace, self).__init__(*args, k8s_kind='Namespace', **kwargs)

    @property
    def argspec(self):
        """ argspec property builder """
        argument_spec = copy.deepcopy(AUTH_ARG_SPEC)
        argument_spec.update(NAMESPACE_ARG_SPEC)
        return argument_spec

    def execute_module(self):
        """ Module execution """
        self.client = self.get_api_client()

        namespace_api = self.find_resource('Namespace', 'v1', fail=True)
        projectrequest_api = self.find_resource('ProjectRequest', 'project.openshift.io/v1', fail=False)

        result = {'changed': False, 'result': {}}
        name = self.params.get('name')
        existing = None

        try:
            existing = namespace_api.get(name)
        except (NotFoundError, ForbiddenError):
            pass
        except DynamicApiError as exc:
            self.fail_json(
                msg='Failed to retrieve Namespace: {0}'.format(exc.body),
                error=exc.status, status=exc.status, reason=exc.reason
            )

        if existing:
            result['result'] = existing.to_dict()

        else:
            result['changed'] = True
            if not self.check_mode:
                try:
                    k8s_obj = namespace_api.create(dict(
                        apiVersion = 'v1',
                        kind = 'Namespace',
                        metadata = dict(
                            name=name
                        )
                    ))
                    result['result'] = k8s_obj.to_dict()
                except (DynamicApiError, ForbiddenError) as exc:
                    if projectrequest_api:
                        try:
                            k8s_obj = projectrequest_api.create(dict(
                                apiVersion = 'project.openshift.io/v1',
                                kind = 'ProjectRequest',
                                metadata = dict(
                                    name=name
                                )
                            ))
                            result['result'] = k8s_obj.to_dict()
                        except (DynamicApiError, ForbiddenError) as exc:
                            self.fail_json(
                                msg='Failed to create ProjectRequest: {0}'.format(exc.body),
                                error=exc.status, status=exc.status, reason=exc.reason
                            )
                    else:
                        self.fail_json(
                            msg='Failed to create Namespace: {0}'.format(exc.body),
                            error=exc.status, status=exc.status, reason=exc.reason
                        )

        self.exit_json(**result)

def main():
    module = KubernetesNamespace()
    try:
        module.execute_module()
    except Exception as e:
        module.fail_json(msg=str(e), exception=traceback.format_exc())

if __name__ == '__main__':
    main()
