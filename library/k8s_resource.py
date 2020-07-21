#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2018, Chris Houseknecht <@chouseknecht>
# (c) 2019, Johnathan Kupferer
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''

module: k8s_resource

short_description: Manage Kubernetes (k8s) resources

version_added: "2.9"

author:
  - "Johnathan Kupferer"

description:
- Use the OpenShift Python client to perform CRUD operations on K8s resources.
- Pass the object definition from a source file or inline. See examples for reading
  files and using Jinja templates or vault-encrypted files.
- Access to the full range of K8s APIs.
- Authenticate using either a config file, certificates, password or token.
- Supports check mode.

extends_documentation_fragment:
- k8s_auth_options
- k8s_name_options
- k8s_resource_options

options:
  action:
    description:
    - Action to perform to converge to desired configuration. By default the C(apply) action will be used.
    - C(apply) will apply resource definitions to create or update resources in manner compatible with C(kubectl apply).
    - C(create) will create resources only if the resources do not exist.
    - C(delete) will delete resources if they exist.
    - C(replace) will create resources if they do not exist or replace them if they do
    - C(merge) and C(strategic-merge) will attempt to create resources if they do not exist and patch them if they do.
    - C(strategic-merge) falls back to attempting merge patch if resource does not support strategic-merge patch.
    choices:
    - apply
    - create
    - delete
    - merge
    - replace
    - strategic-merge
    type: str
    version_added: "2.9"

requirements:
  - "python >= 2.7"
  - "openshift >= 0.6"
  - "PyYAML >= 3.11"
'''

EXAMPLES = '''
- name: Create a k8s namespace
  k8s_resource:
    action: create
    name: testing
    api_version: v1
    kind: Namespace

- name: Create a Service object from an inline definition
  k8s_resource:
    action: apply
    definition:
      apiVersion: v1
      kind: Service
      metadata:
        name: web
        namespace: testing
        labels:
          app: galaxy
          service: web
      spec:
        selector:
          app: galaxy
          service: web
        ports:
        - protocol: TCP
          targetPort: 8000
          name: port-8000-tcp
          port: 8000

- name: Create a Service object by reading the definition from a file
  k8s_resource:
    state: present
    src: /testing/service.yml

- name: Remove an existing Service object
  k8s_resource:
    action: delete
    api_version: v1
    kind: Service
    namespace: testing
    name: web

# Passing the object definition from a file

- name: Create a Deployment by reading the definition from a local file
  k8s:
    state: present
    src: /testing/deployment.yml

- name: >-
    Read definition file from the Ansible controller file system.
    If the definition file has been encrypted with Ansible Vault it will automatically be decrypted.
  k8s:
    state: present
    definition: "{{ lookup('file', '/testing/deployment.yml') }}"

- name: Read definition file from the Ansible controller file system after Jinja templating
  k8s:
    state: present
    definition: "{{ lookup('template', '/testing/deployment.yml') }}"

- name: fail on validation errors
  k8s:
    state: present
    definition: "{{ lookup('template', '/testing/deployment.yml') }}"
    validate:
      fail_on_error: yes

- name: warn on validation errors, check for unexpected properties
  k8s:
    state: present
    definition: "{{ lookup('template', '/testing/deployment.yml') }}"
    validate:
      fail_on_error: no
      strict: yes
'''

RETURN = '''
result:
  description:
  - The resources created, deleted, patched, or found already in the configured state.
  returned: success
  type: complex
  contains:
    resources:
      description: List of resources created, deleted, patched, or found.
      returned: success
      type: list
'''

import copy
from distutils.version import LooseVersion
import sys

from ansible.module_utils.basic import missing_required_lib
from ansible.module_utils.k8s.common import AUTH_ARG_SPEC, COMMON_ARG_SPEC
from ansible.module_utils.six import string_types
from ansible.module_utils.k8s.common import KubernetesAnsibleModule

try:
    import yaml
    from openshift.dynamic.exceptions import \
        DynamicApiError, NotFoundError, ConflictError, ForbiddenError, KubernetesValidateMissing
except ImportError:
    # Exceptions handled in common
    pass

HAS_K8S_APPLY = False
try:
    from openshift.dynamic.apply import apply_object
    HAS_K8S_APPLY = True
except ImportError:
    pass

def deep_merge(source, merge_patch):
    def _dict_merge(result, patch):
        for k, v in patch.items():
            if isinstance(v, dict) and k in result and isinstance(result[k], dict):
                _dict_merge(result[k], v)
            elif isinstance(v, list) and k in result and isinstance(result[k], list):
                _list_merge(result[k], v)
            else:
                result[k] = copy.deepcopy(v)

    def _list_merge(result, patch):
        for i, v in enumerate(patch):
            if isinstance(v, dict) and i < len(result) and isinstance(result[i], dict):
                _dict_merge(result[i], v)
            elif isinstance(v, list) and i < len(result) and isinstance(result[i], list):
                _list_merge(result[i], v)
            else:
                result[k] = copy.deepcopy(v)

    res = copy.deepcopy(source)
    _dict_merge(res, merge_patch)
    return res
    

class KubernetesResourceModule(KubernetesAnsibleModule):

    @property
    def argspec(self):
        argument_spec = copy.deepcopy(COMMON_ARG_SPEC)
        argument_spec.update(copy.deepcopy(AUTH_ARG_SPEC))
        argument_spec['action'] = dict(
            type='str',
            choices=['apply', 'create', 'delete', 'merge', 'replace', 'strategic-merge'],
            default='apply',
        )
        return argument_spec

    def __init__(self, *args, **kwargs):
        self.client = None

        mutually_exclusive = [
            ('resource_definition', 'src'),
        ]

        KubernetesAnsibleModule.__init__(
            self, *args,
            mutually_exclusive=mutually_exclusive,
            supports_check_mode=True,
            **kwargs
        )

        self.action = self.params.get('action')
        self.kind = self.params.get('kind')
        self.api_version = self.params.get('api_version')
        self.name = self.params.get('name')
        self.namespace = self.params.get('namespace')
        if self.action in ('merge', 'stategic-merge'):
            if LooseVersion(self.openshift_version) < LooseVersion("0.6.2"):
                self.fail_json(msg=missing_required_lib("openshift >= 0.6.2", reason="for action "+self.action))
        if self.action == 'apply':
            if not HAS_K8S_APPLY:
                    self.fail_json(msg=missing_required_lib("openshift >= 0.9.2", reason="for action apply"))

        src = self.params.get('src')
        resource_definition = self.params.get('resource_definition')
        resource_definitions = []

        if resource_definition:
            if isinstance(resource_definition, string_types):
                try:
                    resource_definitions = yaml.safe_load_all(resource_definition)
                except (IOError, yaml.YAMLError) as exc:
                    self.fail(msg="Error loading resource_definition: {0}".format(exc))
            elif isinstance(resource_definition, list):
                resource_definitions = resource_definition
            else:
                resource_definitions = [resource_definition]
        elif src:
            resource_definitions = self.load_resource_definitions(src)
        else:
            resource_definitions = [dict(
                kind=self.kind,
                apiVersion=self.api_version,
                metadata=dict(name=self.name)
            )]

        self.resource_definitions = [item for item in resource_definitions if item]

    def flatten_list_kind(self, list_resource, definitions):
        flattened = []
        parent_api_version = list_resource.group_version if list_resource else None
        parent_kind = list_resource.kind[:-4] if list_resource else None
        for definition in definitions.get('items', []):
            resource = self.find_resource(definition.get('kind', parent_kind), definition.get('apiVersion', parent_api_version), fail=True)
            flattened.append((resource, self.set_defaults(resource, definition)))
        return flattened

    def execute_module(self):
        changed = False
        resources = []
        self.client = self.get_api_client()

        flattened_definitions = []
        for definition in self.resource_definitions:
            kind = definition.get('kind', self.kind)
            api_version = definition.get('apiVersion', self.api_version)
            if kind.endswith('List'):
                resource = self.find_resource(kind, api_version, fail=False)
                flattened_definitions.extend(self.flatten_list_kind(resource, definition))
            else:
                resource = self.find_resource(kind, api_version, fail=True)
                flattened_definitions.append((resource, definition))

        for (resource, definition) in flattened_definitions:
            definition = self.set_defaults(resource, definition)
            resource, resource_changed = self.perform_action(resource, definition)
            if resource_changed:
                changed = True
            resources.append(resource)

        self.exit_json(
            changed=changed,
            resources=resources,
        )

    def set_defaults(self, resource, definition):
        definition['kind'] = resource.kind
        definition['apiVersion'] = resource.group_version
        metadata = definition.get('metadata', {})
        if self.name:
            metadata['name'] = self.name
        if resource.namespaced and self.namespace:
            metadata['namespace'] = self.namespace
        definition['metadata'] = metadata
        return definition

    def perform_action(self, resource, definition):
        name = definition['metadata'].get('name')
        namespace = definition['metadata'].get('namespace')
        existing = None

        try:
            params = dict(name=name)
            if namespace:
                params['namespace'] = namespace
            existing = resource.get(**params)
        except NotFoundError:
            # Remove traceback so that it doesn't show up in later failures
            try:
                sys.exc_clear()
            except AttributeError:
                # no sys.exc_clear on python3
                pass
        except (DynamicApiError, ForbiddenError) as exc:
            self.fail_json(
                msg='Failed to retrieve requested object: {0}'.format(exc.body),
                error=exc.status, status=exc.status, reason=exc.reason
            )

        if self.action == 'apply':
            return self.perform_apply(resource, definition, existing)
        elif self.action == 'delete':
            if existing:
                return self.perform_delete(resource, existing)
            else:
                return None, False
        elif self.action == 'create':
            return self.perform_create(resource, definition, existing)
        elif not existing:
            return self.perform_create(resource, definition, None, fail_on_conflict=True)
        elif self.action == 'merge':
            return self.perform_patch(resource, definition, existing)
        elif self.action == 'replace':
            return self.perform_replace(resource, definition, existing)
        elif self.action == 'strategic-merge':
            return self.perform_patch(resource, definition, existing, strategic_merge=True)

    def perform_apply(self, resource, definition, existing):
        namespace = definition['metadata'].get('namespace')
        if self.check_mode:
            ignored, k8s_obj = apply_object(resource, definition)
        else:
            try:
                k8s_obj = resource.apply(definition, namespace=namespace).to_dict()
            except DynamicApiError as exc:
                self.fail_json(
                    msg="Failed to apply object: {0}".format(exc.body),
                    error=exc.status, status=exc.status, reason=exc.reason
                )
        existing = existing.to_dict() if existing else {}
        match, diffs = self.diff_objects(existing, k8s_obj)
        return k8s_obj, not match

    def perform_create(self, resource, definition, existing, fail_on_conflict=False):
        namespace = definition['metadata'].get('namespace')
        if existing:
            return existing.to_dict(), False
        if self.check_mode:
            return definition, True
        try:
            k8s_obj = resource.create(definition, namespace=namespace).to_dict()
            return k8s_obj, True
        except ConflictError:
            # Some resources, like ProjectRequests, can't be created multiple times,
            # because the resources that they create don't match their kind
            # In this case we'll mark it as unchanged and warn the user
            if fail_on_conflict:
                self.fail_json(
                    msg="Failed to create object: {0}".format(exc.body),
                    error=exc.status, status=exc.status, reason=exc.reason
                )
            else:
                self.warn(
                    "{0} was not found, but creating it returned a 409 Conflict error. "
                    "This can happen if the resource you are creating does not directly "
                    "create a resource of the same kind.".format(name)
                )
                return None, False
        except DynamicApiError as exc:
            self.fail_json(
                msg="Failed to create object: {0}".format(exc.body),
                error=exc.status, status=exc.status, reason=exc.reason
            )

    def perform_delete(self, resource, existing):
        params = dict(name=existing.metadata.name)
        if hasattr(existing, 'namespace'):
            params['namespace'] = existing.metadata.namespace
        if not existing:
            return None, False
        if self.check_mode:
            return existing.to_dict(), True
        try:
            k8s_obj = resource.delete(**params).to_dict()
            return k8s_obj, True
        except DynamicApiError as exc:
            self.fail_json(
                msg="Failed to delete object: {0}".format(exc.body),
                error=exc.status, status=exc.status, reason=exc.reason
            )

    def perform_patch(self, resource, definition, existing, strategic_merge=False):
        name = definition['metadata'].get('name')
        namespace = definition['metadata'].get('namespace')
        merged_definition = deep_merge(existing.to_dict(), definition)
        k8s_obj = None
        if self.check_mode:
            k8s_obj = merged_definition
        else:
            params = dict(name=name)
            if namespace:
                params['namespace'] = namespace
            if strategic_merge:
                params['content_type'] = 'application/strategic-merge-patch+json'
                try:
                    k8s_obj = resource.patch(definition, **params).to_dict()
                except DynamicApiError as exc:
                    pass
            if not k8s_obj:
                params['content_type'] = 'application/merge-patch+json'
                try:
                    k8s_obj = resource.patch(definition, **params).to_dict()
                except DynamicApiError as exc:
                   self.fail_json(
                       msg="Failed to patch object: {0}".format(exc.body),
                       error=exc.status, status=exc.status, reason=exc.reason
                   )
        match, diffs = self.diff_objects(existing.to_dict(), k8s_obj)
        return k8s_obj, not match

    def perform_replace(self, resource, definition, existing):
        name = definition['metadata'].get('name')
        namespace = definition['metadata'].get('namespace')
        if self.check_mode:
            k8s_obj = definition
        else:
            try:
                k8s_obj = resource.replace(definition, name=name, namespace=namespace).to_dict()
            except DynamicApiError as exc:
                self.fail_json(
                    msg="Failed to replace object: {0}".format(exc.body),
                    error=exc.status, status=exc.status, reason=exc.reason
                )
        match, diffs = self.diff_objects(existing.to_dict(), k8s_obj)
        return k8s_obj, not match


def main():
    KubernetesResourceModule().execute_module()

if __name__ == '__main__':
    main()
