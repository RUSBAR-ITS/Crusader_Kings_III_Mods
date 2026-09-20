"""Build-time helper shared by the two independent runtime patches."""
import re
from ScriptBlocks import one, edit, semantic

CROWN_SOURCE = 'common/scripted_effects/00_agot_artifact_crowns_effects.txt'
PLUS_CROWNS = ('aegon_i_crown', 'aenys_crown', 'jaehaerys_crown', 'aegon_iii_crown',
               'baelors_crown', 'aegon_iv_crown', 'maekars_crown')
LOTD_CROWNS = ('aenys_crown', 'aegon_iii_crown', 'baelors_crown', 'maekars_crown', 'visenya_circlet')


def function_names(names, prefix):
    return {'agot_create_artifact_'+name+'_effect':
            prefix+'_create_artifact_'+name+'_without_creator_effect' for name in names}


def make_helpers(source, names, prefix):
    out = ['# Generated from current AGOT crown effects.\n'
           '# Automatic grants/finds have no known maker; preserve OWNER and all artifact properties.']
    for old, new in function_names(names, prefix).items():
        node = one(source, old)
        binding = node.one('$CREATOR$')
        creation = node.one('create_artifact')
        field = creation.one('creator')
        assert binding.one('save_scope_as').value == 'creator'
        assert field.value == 'scope:creator'
        assert set(re.findall(r'\$([A-Z_]+)\$', source[node.start:node.end])) == {'OWNER', 'CREATOR'}
        text = edit(source[node.start:node.end], [
            (n.start-node.start, n.end-node.start, '') for n in (binding, field)])
        text = text.replace(old, new, 1)
        text = '\n'.join(line.rstrip() for line in text.splitlines())
        candidate = one(text, new)
        expected = semantic(node)
        expected = (new, expected[1], [
            (child.key, child.op, [semantic(n) for n in child.value if n is not field])
            if child is creation else semantic(child)
            for child in node.value if child is not binding])
        assert semantic(candidate) == expected, old
        assert set(re.findall(r'\$([A-Z_]+)\$', text)) == {'OWNER'}
        assert 'scope:creator' not in text and '$CREATOR$' not in text
        out.append(text)
    return '\n\n'.join(out)+'\n'
