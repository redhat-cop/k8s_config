#!/usr/bin/env python

import copy
import unittest

import sys
sys.path.append('../library')

import k8s_json_patch

deployment = {
    'apiVersion': 'apps/v1',
    'kind': 'Deployment',
    'metadata': {
        'name': 'myapp'
    },
    'spec': {
        'replicas': 1,
        'selector': {
            'matchLabels': {
                'name': 'myapp'
            }
        },
        'strategy': {
            'type': 'Recreate'
        },
        'template': {
            'metadata': {
                'labels': {
                    'name': 'myapp'
                }
            },
            'spec': {
                'containers': [{
                    'name': 'app',
                    'env': [{
                        'name': 'VAR1',
                        'value': 'value1'
                    },{
                        'name': 'VAR2',
                        'value': 'value2'
                    }],
                    'image': 'example.com/example/image:latest',
                    'resources': {
                        'limits': {
                            'cpu': '500m',
                            'memory': '200Mi'
                        },
                        'requests': {
                            'cpu': '100m',
                            'memory': '200Mi'
                        }
                    }
                }]
            }
        }
    }
}

class TestJsonPatchResolvePath(unittest.TestCase):
    def test_00_simple_resolve_path(self):
        path_list = k8s_json_patch.path_to_list('/metadata/name')
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, 'myapp')
        self.assertEqual(context, deployment['metadata'])
        self.assertEqual(key, 'name')
        self.assertEqual(matched_path, ['metadata','name'])
        self.assertEqual(unmatched_path, [])

    def test_01_list_resolve_path(self):
        path_list = k8s_json_patch.path_to_list('/spec/template/spec/containers/0/env/0')
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, {'name': 'VAR1', 'value': 'value1'})
        self.assertEqual(context, deployment['spec']['template']['spec']['containers'][0]['env'])
        self.assertEqual(key, 0)
        self.assertEqual(matched_path, ['spec','template','spec','containers','0','env','0'])
        self.assertEqual(unmatched_path, [])

    def test_02_deep_resolve_path(self):
        path_list = k8s_json_patch.path_to_list('/spec/template/spec/containers/0/env/0/value')
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, 'value1')
        self.assertEqual(context, deployment['spec']['template']['spec']['containers'][0]['env'][0])
        self.assertEqual(key, 'value')
        self.assertEqual(matched_path, ['spec','template','spec','containers','0','env','0','value'])
        self.assertEqual(unmatched_path, [])

    def test_03_query_resolve_path(self):
        path_list = k8s_json_patch.path_to_list("/spec/template/spec/containers/[?name='app']/env/[?name='VAR2']")
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, {'name': 'VAR2', 'value': 'value2'})
        self.assertEqual(context, deployment['spec']['template']['spec']['containers'][0]['env'])
        self.assertEqual(key, 1)
        self.assertEqual(matched_path, ['spec','template','spec','containers','0','env','1'])
        self.assertEqual(unmatched_path, [])

    def test_04_query_resolve_path(self):
        path_list = k8s_json_patch.path_to_list("/spec/template/spec/containers/[?name='app']/env/[?name='VAR2']/value")
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, 'value2')
        self.assertEqual(context, deployment['spec']['template']['spec']['containers'][0]['env'][1])
        self.assertEqual(key, 'value')
        self.assertEqual(matched_path, ['spec','template','spec','containers','0','env','1','value'])
        self.assertEqual(unmatched_path, [])

    def test_05_unmatched_resolve_path(self):
        path_list = k8s_json_patch.path_to_list('/metadata/labels/name')
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, None)
        self.assertEqual(context, deployment['metadata'])
        self.assertEqual(key, 'labels')
        self.assertEqual(matched_path, ['metadata'])
        self.assertEqual(unmatched_path,  ['labels','name'])

    def test_06_unmatched_resolve_path(self):
        path_list = k8s_json_patch.path_to_list("/spec/template/spec/containers/[?name='nomatch']")
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, None)
        self.assertEqual(context, deployment['spec']['template']['spec']['containers'])
        self.assertEqual(key, "[?name='nomatch']")
        self.assertEqual(matched_path, ['spec','template','spec','containers'])
        self.assertEqual(unmatched_path,  ["[?name='nomatch']"])

    def test_07_unmatched_resolve_path(self):
        path_list = k8s_json_patch.path_to_list("/spec/template/spec/containers/[?name='app']/env/[?name='NOSUCH']/value")
        value, context, key, matched_path, unmatched_path = k8s_json_patch.resolve_path(deployment, path_list)
        self.assertEqual(value, None)
        self.assertEqual(context, deployment['spec']['template']['spec']['containers'][0]['env'])
        self.assertEqual(key, "[?name='NOSUCH']")
        self.assertEqual(matched_path, ['spec','template','spec','containers','0','env'])
        self.assertEqual(unmatched_path,  ["[?name='NOSUCH']", 'value'])

class TestJsonPatchAdd(unittest.TestCase):
    def test_00(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_add({
            'op': 'add',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
            'value': 'updated'
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, {
            'op': 'replace',
            'path': '/spec/template/spec/containers/0/env/0/value',
            'value': 'updated'
        })
        self.assertEqual(
            deployment_copy['spec']['template']['spec']['containers'][0]['env'][0],
            {'name': 'VAR1', 'value': 'updated'}
        )

    def test_01(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_add({
            'op': 'add',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='NEWVAR']/value",
            'value': 'new'
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, {
            'op': 'add',
            'path': '/spec/template/spec/containers/0/env/-',
            'value': {'name': 'NEWVAR', 'value': 'new'}
        })
        self.assertEqual(
            deployment_copy['spec']['template']['spec']['containers'][0]['env'][2],
            {'name': 'NEWVAR', 'value': 'new'}
        )

    def test_02(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_add({
            'op': 'add',
            'path': "/spec/template/spec/containers/[?name='app']/env/99",
            'value': {'name': 'NEWVAR', 'value': 'new'}
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, {
            'op': 'add',
            'path': '/spec/template/spec/containers/0/env/-',
            'value': {'name': 'NEWVAR', 'value': 'new'}
        })
        self.assertEqual(
            deployment_copy['spec']['template']['spec']['containers'][0]['env'][2],
            {'name': 'NEWVAR', 'value': 'new'}
        )

    def test_03(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_add({
                'op': 'add',
                'path': '/spec/template/spec/containers/badpath',
                'value': 'willfail'
            }, deployment_copy)

    def test_04(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_add({
                'op': 'add',
                'path': '/spec/template/spec/containers/0/env/0/value',
                'replace': False,
                'value': 'willfail'
            }, deployment_copy)

    def test_05(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_add({
            'op': 'add',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
            'value': 'value1'
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, None)

class TestJsonPatchRemove(unittest.TestCase):
    def test_00(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_remove({
            'op': 'remove',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR2']"
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, {
            'op': 'remove',
            'path': '/spec/template/spec/containers/0/env/1'
        })
        self.assertTrue(
            len(deployment_copy['spec']['template']['spec']['containers'][0]['env']) == 1
        )

    def test_01(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_remove({
            'op': 'remove',
            'path': "/spec/labels/nolabel"
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, None)

class TestJsonPatchReplace(unittest.TestCase):
    def test_00(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_replace({
            'op': 'replace',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
            'value': 'updated'
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, {
            'op': 'replace',
            'path': '/spec/template/spec/containers/0/env/0/value',
            'value': 'updated'
        })
        self.assertEqual(
            deployment_copy['spec']['template']['spec']['containers'][0]['env'][0],
            {'name': 'VAR1', 'value': 'updated'}
        )

    def test_01(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_replace({
                'op': 'replace',
                'path': '/spec/labels/nolabel',
                'value': 'willfail'
            }, deployment_copy)

class TestJsonPatchTest(unittest.TestCase):
    def test_00(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_test({
            'op': 'test',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
            'value': 'value1'
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, {
            'op': 'test',
            'path': '/spec/template/spec/containers/0/env/0/value',
            'value': 'value1'
        })

    def test_01(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_test({
                'op': 'test',
                'path': '/spec/labels/nolabel',
                'value': 'willfail'
            }, deployment_copy)

    def test_02(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_test({
                'op': 'test',
                'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
                'value': 'willfail'
            }, deployment_copy)

    def test_03(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_test({
                'op': 'test',
                'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
                'state': 'absent'
            }, deployment_copy)

    def test_04(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_test({
                'op': 'test',
                'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
                'state': 'unequal',
                'value': 'value1'
            }, deployment_copy)

    def test_05(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_test({
            'op': 'test',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR3']/value",
            'state': ['unequal', 'absent'],
            'value': 'value3'
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, None)

class TestJsonPatchCopy(unittest.TestCase):
    def test_00(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_copy({
            'op': 'copy',
            'from': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']",
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR3']"
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, {
            'op': 'add',
            'path': '/spec/template/spec/containers/0/env/-',
            'value': {'name': 'VAR3', 'value': 'value1'}
        })

    def test_01(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_copy({
                'op': 'copy',
                'from': "/spec/template/spec/containers/[?name='app']/env/[?name='NOFIND']",
                'path': "/spec/template/spec/containers/[?name='app']/env/[?name='WILLFAIL']"
            }, deployment_copy)

class TestJsonPatchMove(unittest.TestCase):
    def test_00(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch_operation = k8s_json_patch.process_patch_move({
            'op': 'copy',
            'from': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']",
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR3']"
        }, deployment_copy)
        self.assertEqual(processed_patch_operation, [{
            'op': 'remove',
            'path': '/spec/template/spec/containers/0/env/0',
        },{
            'op': 'add',
            'path': '/spec/template/spec/containers/0/env/-',
            'value': {'name': 'VAR3', 'value': 'value1'}
        }])

    def test_01(self):
        with self.assertRaises(k8s_json_patch.JsonPatchFailException):
            deployment_copy = copy.deepcopy(deployment)
            k8s_json_patch.process_patch_copy({
                'op': 'copy',
                'from': "/spec/template/spec/containers/[?name='app']/env/[?name='NOFIND']",
                'path': "/spec/template/spec/containers/[?name='app']/env/[?name='WILLFAIL']"
            }, deployment_copy)

class TestJsonPatch(unittest.TestCase):
    def test_00(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch, patched_obj = k8s_json_patch.process_patch([{
            'op': 'add',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
            'value': 'replaced'
        }], deployment_copy)
        self.assertEqual(processed_patch, [{
            'op': 'replace',
            'path': "/spec/template/spec/containers/0/env/0/value",
            'value': 'replaced'
        }])
        self.assertEqual('replaced', patched_obj['spec']['template']['spec']['containers'][0]['env'][0]['value'])

    def test_01(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch, patched_obj = k8s_json_patch.process_patch([{
            'op': 'test',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
            'state': 'absent',
            'operations': [{
                'op': 'add',
                'value': 'should-be-skipped'
            }]
        }], deployment_copy)
        self.assertEqual(processed_patch, [])
        self.assertEqual('value1', patched_obj['spec']['template']['spec']['containers'][0]['env'][0]['value'])

    def test_02(self):
        deployment_copy = copy.deepcopy(deployment)
        processed_patch, patched_obj = k8s_json_patch.process_patch([{
            'op': 'test',
            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
            'state': 'present',
            'operations': [{
                'op': 'add',
                'value': 'replaced'
            }]
        }], deployment_copy)
        self.assertEqual(processed_patch, [{
            'op': 'replace',
            'path': '/spec/template/spec/containers/0/env/0/value',
            'value': 'replaced'
        }])
        self.assertEqual('replaced', patched_obj['spec']['template']['spec']['containers'][0]['env'][0]['value'])

    #def test_03(self):
    #    deployment_copy = copy.deepcopy(deployment)
    #    processed_patch, patched_obj = k8s_json_patch.process_patch([{
    #        'op': 'test',
    #        'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR1']/value",
    #        'state': 'present',
    #        'operations': [{
    #            'op': 'add',
    #            'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR3']/value",
    #            'value': 'new'
    #        }]
    #    }], deployment_copy)
    #    self.assertEqual(processed_patch, [])
    #    self.assertEqual('new', patched_obj['spec']['template']['spec']['containers'][0]['env'][2]['value'])

    #def test_04(self):
    #    deployment_copy = copy.deepcopy(deployment)
    #    processed_patch, patched_obj = k8s_json_patch.process_patch([{
    #        'op': 'add',
    #        'path': "/spec/template/spec/containers/[?name='app']/env/[?name='VAR3']/value",
    #        'value': 'updated',
    #        'test': {
    #            'state': 'absent'
    #        }
    #    }], deployment_copy)
    #    self.assertEqual(processed_patch, [{
    #        'op': 'add',
    #        'path': '/spec/template/spec/containers/0/env/-',
    #        'value': {'name': 'VAR3', 'value': 'updated'}
    #    }])
    #    self.assertEqual('updated', patched_obj['spec']['template']['spec']['containers'][0]['env'][2]['value'])

if __name__ == '__main__':
    unittest.main()
