"""W1.28 — JSON printed into a <script> can't close the tag."""

from django.test import SimpleTestCase

from apps.core.script_json import script_json


class ScriptJsonTests(SimpleTestCase):
    def test_a_closing_script_tag_in_a_value_is_escaped(self):
        out = script_json({'read': 'COUNTY No. 46 </script><script>alert(1)</script>'})
        self.assertNotIn('</script>', out)
        self.assertIn('\\u003C/script\\u003E', out)

    def test_it_is_still_the_same_json(self):
        import json
        value = {'a': '<b> & </b>', 'n': [1, 2]}
        self.assertEqual(json.loads(script_json(value)), value)
