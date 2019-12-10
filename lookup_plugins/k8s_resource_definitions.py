# Copyright: (c) 2019, Johnathan Kupferer <jkupfere@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = """
    lookup: k8s_resource_definitions
    author: Johnathan kupferer <jkupfere@redhat.com>
    version_added: "2.9"
    short_description: Resolve kubernetes resource definitions
    description:
    - Returns a list of kubernetes resources from files, templates, etc.
    options:
      _terms:
        description: list of template sources
"""

EXAMPLES = """
- name: show templating results
  debug:
    msg: "{{ lookup('k8s_resource_definitions', source_list) }}"
"""

RETURN = """
_raw:
   description: k8s resource definitions
"""

from copy import deepcopy
import os
import requests
import subprocess
import tempfile
import yaml

from ansible.errors import AnsibleError, AnsibleParserError
from ansible.module_utils._text import to_text
from ansible.plugins.lookup import LookupBase
from ansible.template import generate_ansible_template_vars
from ansible.utils.display import Display

display = Display()

class LookupModule(LookupBase):
    def from_definition(self, definition):
        if definition['kind'] == 'List' and definition['apiVersion'] == 'v1':
            return definition.get('items', [])
        else:
            return [definition]

    def from_file(self, filename, searchpath):
        lookupfile = self._loader.path_dwim_relative_stack(searchpath, 'files', filename)
        b_contents, show_data = self._loader._get_file_contents(lookupfile)
        contents = to_text(b_contents, errors='surrogate_or_strict')
        ret = []
        for yaml_document in yaml.safe_load_all(contents):
            ret.extend(self.from_definition(yaml_document))
        return ret

    def from_template(self, template, searchpath, variables):
        template_file = template['file']
        template_vars = template.get('vars', {})

        lookupfile = self._loader.path_dwim_relative_stack(searchpath, 'templates', template_file)
        b_template_data, show_data = self._loader._get_file_contents(lookupfile)
        template_data = to_text(b_template_data, errors='surrogate_or_strict')

        # set jinja2 internal search path for includes
        template_searchpath = [
            os.path.join(item, 'templates') for item in searchpath
        ]
        template_searchpath.insert(0, os.path.dirname(lookupfile))

        self._templar.environment.loader.searchpath = searchpath

        vars = deepcopy(variables)
        vars.update(generate_ansible_template_vars(lookupfile))
        vars.update(template_vars)
        self._templar.available_variables = vars

        res = self._templar.template(
            template_data, preserve_trailing_newlines=True,
            convert_data=True, escape_backslashes=False
        )
        ret = []
        for yaml_document in yaml.safe_load_all(res):
            ret.extend(self.from_definition(yaml_document))
        return ret

    def from_url(self, url):
        try:
            resp = requests.get(url)
        except Exception as err:
            raise AnsibleError('Failed to fetch {}: {}'.format(url, err))
        ret = []
        for yaml_document in yaml.safe_load_all(resp.text):
            ret.extend(self.from_definition(yaml_document))
        return ret

    def run(self, terms, variables=None, **kwargs):
        ret = []
        searchpath = variables.get('k8s_config_search_path', []).copy()
        searchpath.extend(variables.get('ansible_search_path', []))

        for term in terms:
            if 'definition' in term:
                ret.extend(self.from_definition(term['definition']))
            elif 'file' in term:
                ret.extend(self.from_file(term['file'], searchpath))
            elif 'template' in term:
                ret.extend(self.from_template(term['template'], searchpath, variables))
            elif 'url' in term:
                ret.extend(self.from_url(term['url']))
            else:
                raise AnsibleError('Unknown resource definition: {}'.format(term))

        return ret
