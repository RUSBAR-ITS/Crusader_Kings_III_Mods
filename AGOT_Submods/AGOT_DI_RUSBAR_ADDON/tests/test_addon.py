"""Static and model tests. These do not execute the CK3 engine or render its GUI.

Run: python -X utf8 -m unittest discover -s AGOT_Submods/AGOT_DI_RUSBAR_ADDON/tests -v
Reference-trait checks use the installed vanilla/AGOT traits when available.
"""
from pathlib import Path
import copy
import random
import re
import unittest

BASE = Path(__file__).resolve().parents[1]
PREFIX = 'agot_di_rusbar_'
TOKEN = re.compile(r'#[^\n]*|"(?:\\.|[^"\\])*"|>=|<=|!=|\?=|[{}=<>]|[^\s{}=<>]+')


def parse(path):
    tokens = [m[0] for m in TOKEN.finditer(path.read_text(encoding='utf-8-sig')) if not m[0].startswith('#')]
    i = 0

    def items():
        nonlocal i
        out = []
        while i < len(tokens) and tokens[i] != '}':
            key = tokens[i]
            i += 1
            op, value = '', None
            if i < len(tokens) and tokens[i] in ('=', '>=', '<=', '!=', '?=', '>', '<'):
                op = tokens[i]
                i += 1
                if tokens[i] in ('rgb', 'hsv', 'hsv360'):
                    i += 1
                if tokens[i] == '{':
                    i += 1
                    value = items()
                    assert tokens[i] == '}', path
                    i += 1
                else:
                    value = tokens[i].strip('"')
                    i += 1
            out.append((key, op, value))
        return out

    result = items()
    assert i == len(tokens), (path, i, len(tokens))
    return result


def walk(nodes):
    for n in nodes:
        yield n
        if isinstance(n[2], list):
            yield from walk(n[2])


def field(nodes, key, default=None):
    return next((v for k, _, v in nodes if k == key), default)


def definitions(folder):
    return {k: v for f in (BASE / folder).glob('*.txt') for k, _, v in parse(f)}


EFFECTS = definitions('common/scripted_effects')
TRIGGERS = definitions('common/scripted_triggers')
INTERACTIONS = definitions('common/character_interactions')
SGUIS = definitions('common/scripted_guis')
GAME_RULES = definitions('common/game_rules')
INNOVATIONS = definitions('common/culture/innovations')


def on_action_definitions():
    """CK3 appends child on_actions from separate files to the same native hook."""
    result = {}
    for path in (BASE / 'common/on_action').glob('*.txt'):
        for name, _, nodes in parse(path):
            if name in result:
                assert not name.startswith(PREFIX), ('Duplicate addon handler', name)
                assert all(k == 'on_actions' for k, _, _ in nodes + result[name]), name
                children = field(result[name], 'on_actions') + field(nodes, 'on_actions')
                result[name] = [('on_actions', '=', children)]
            else:
                result[name] = nodes
    return result


ON_ACTIONS = on_action_definitions()
SKILLS = ('diplomacy', 'martial', 'stewardship', 'intrigue', 'learning', 'prowess')
PROFILES = {k: v for k, v in EFFECTS.items() if k.startswith(PREFIX + 'prepare_')}
# AGOT 0.5.2.1 human personality category, independently checked against the installation.
PERSONALITY_TRAITS = set('''ambitious arbitrary arrogant authoritative brave callous calm
chaste compassionate content craven cynical deceitful diligent eccentric fickle forgiving
generous gluttonous greedy gregarious honest humble impatient inquisitive just lazy lustful
paranoid patient rude sadistic shy stubborn temperate trusting vengeful wrathful zealous'''.split())


class Character:
    """Small interpreter for character-profile effects, assuming engine skill/XP clamps.

    Native appointment and scoped world predicates are deliberately not simulated.
    Tests of those paths below check the presence/order of the native guards instead.
    """

    def __init__(self, base=0, traits=(), female=True, monastic=False, seed=0):
        self.skills = dict.fromkeys(SKILLS, base)
        self.traits = set(traits)
        self.xp = {}
        self.languages = set()
        self.flags = set()
        self.variables = {}
        self.modifiers = set()
        self.female = female
        self.monastic = monastic
        self.seed = seed
        self.random_choices = 0

    def test(self, nodes):
        def one(k, op, v):
            if k in ('AND', 'limit', 'custom_tooltip'):
                return self.test(v)
            if k == 'OR':
                return any(one(*n) for n in v)
            if k == 'NOR':
                return not any(one(*n) for n in v)
            if k == 'NOT':
                return not self.test(v)
            if k in ('text', 'desc'):
                return True
            if k == 'has_trait':
                return v in self.traits
            if k == 'number_of_personality_traits':
                count = len(self.traits & PERSONALITY_TRAITS)
                return {'<': count < int(v), '>=': count >= int(v), '=': count == int(v)}[op]
            if k == 'is_eunuch_trigger':
                return bool(self.traits & {'eunuch_1', 'beardless_eunuch'}) == (v == 'yes')
            if k == 'has_commander_trait_trigger':
                return bool(self.traits & {'organizer', 'military_engineer', 'reckless', 'cautious_leader'}) == (v == 'yes')
            if k in ('is_female', 'is_male'):
                value = self.female if k == 'is_female' else not self.female
                return value == (v == 'yes')
            if k == 'culture':
                return self.test(v)
            if k == 'has_cultural_parameter':
                return self.monastic if v == 'devoted_trait_bonuses' else False
            if k == 'has_character_modifier':
                return v in self.modifiers
            if k == 'knows_language':
                return v in self.languages
            if k == 'has_variable':
                return v in self.variables
            # World/title/council branches cannot be established by this model.
            if k.startswith(('scope:', 'liege', 'primary_title', 'has_title', 'has_council_position')):
                return False
            raise AssertionError(('Unhandled model predicate', k, op, v))

        return all(one(*n) for n in nodes)

    def run(self, name, parameters=None):
        def substitute(nodes):
            def string(value):
                for key, replacement in parameters.items():
                    value = value.replace('$' + key + '$', replacement)
                return value
            return [(string(k), op, substitute(v) if isinstance(v, list) else string(v) if isinstance(v, str) else v)
                    for k, op, v in nodes]
        self.apply(substitute(EFFECTS[name]) if parameters else EFFECTS[name])
        return self

    def apply(self, nodes):
        taken = False
        for k, _, v in nodes:
            if k in ('if', 'else_if', 'else'):
                if k == 'if':
                    taken = False
                if not taken and (k == 'else' or self.test(field(v, 'limit', []))):
                    self.apply([n for n in v if n[0] != 'limit'])
                    taken = True
                continue
            if k in EFFECTS:
                self.run(k, {key: value for key, _, value in v} if isinstance(v, list) else None)
            elif k.startswith('add_') and k.endswith('_skill'):
                stat = k[4:-6]
                delta = 100 if v.startswith('define:NSkills|MAX_') else int(v)
                self.skills[stat] = max(0, min(100, self.skills[stat] + delta))
            elif k == 'remove_trait':
                self.traits.discard(v)
            elif k == 'add_trait':
                self.traits.add(v)
            elif k == 'make_trait_inactive':
                self.traits.discard(v)
                self.flags.add('inactive:' + v)
            elif k == 'add_trait_xp':
                trait, track = field(v, 'trait'), field(v, 'track', '')
                assert trait in self.traits, ('XP without active trait', trait)
                self.xp[trait, track] = min(100, self.xp.get((trait, track), 0) + int(field(v, 'value')))
            elif k == 'learn_language':
                self.languages.add(v)
            elif k == 'add_character_flag':
                self.flags.add(v)
            elif k == 'add_character_modifier':
                self.modifiers.add(field(v, 'modifier'))
            elif k == 'set_variable':
                self.variables[field(v, 'name')] = field(v, 'value')
            elif k == 'random_list':
                eligible = [(int(weight), branch) for weight, _, branch in v
                            if self.test(field(branch, 'trigger', []))]
                if eligible:
                    rng = random.Random(self.seed + self.random_choices)
                    branch = rng.choices([b for _, b in eligible], weights=[w for w, _ in eligible])[0]
                    self.random_choices += 1
                    self.apply([n for n in branch if n[0] != 'trigger'])
            elif k == 'while':
                for _ in range(int(field(v, 'count'))):
                    if not self.test(field(v, 'limit', [])):
                        break
                    self.apply([n for n in v if n[0] not in ('count', 'limit')])
            else:
                raise AssertionError(('Unhandled model effect', k, v))


class AddonTests(unittest.TestCase):
    def test_parse_and_text_format(self):
        files = list((BASE / 'common').rglob('*.txt'))
        self.assertGreater(len(files), 10)
        for f in files:
            with self.subTest(file=f.name):
                self.assertTrue(parse(f))
                self.assertNotIn(b'\r', f.read_bytes())
        for f in (BASE / 'localization').rglob('*.yml'):
            with self.subTest(file=f.name):
                data = f.read_bytes()
                self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
                self.assertNotIn(b'\r', data)
                decoded = data.decode('utf-8-sig')
                self.assertNotIn('\ufffd', decoded, f)
                self.assertNotRegex(decoded, r'\?{3,}', f)

    def test_localization_and_internal_symbols(self):
        languages = {}
        for lang in ('russian', 'english'):
            keys = []
            for f in (BASE / 'localization' / lang).glob('*.yml'):
                keys += re.findall(r'^ ([^ :]+):', f.read_text(encoding='utf-8-sig'), re.M)
            self.assertEqual(len(keys), len(set(keys)), lang)
            languages[lang] = set(keys)
        self.assertEqual(languages['russian'], languages['english'])
        for f in (BASE / 'gui').glob('*.gui'):
            text = f.read_text(encoding='utf-8-sig')
            self.assertNotIn('\r', f.read_bytes().decode('utf-8-sig'))
            for name in re.findall(r"GetScriptedGui\('([^']+)'\)", text):
                # The county-view override also retains AGOT's own GUI calls.
                if name.startswith(PREFIX):
                    self.assertIn(name, SGUIS, f)
            for name in re.findall(r'(?:text|tooltip)\s*=\s*"(agot_di_rusbar_[^"\s]+)"', text):
                self.assertIn(name, languages['russian'], f)
            level = 0
            for token in TOKEN.finditer(text):
                if token[0] == '{':
                    level += 1
                elif token[0] == '}':
                    level -= 1
                    self.assertGreaterEqual(level, 0, f)
            self.assertEqual(level, 0, f)
        for f in (BASE / 'common').rglob('*.txt'):
            for k, _, v in walk(parse(f)):
                if k in ('desc', 'text', 'localization', 'custom_tooltip', 'options_heading') and isinstance(v, str) and v.startswith(PREFIX):
                    self.assertIn(v, languages['russian'], (f, k))
        self.assertEqual(len(INTERACTIONS), 10)
        symbols = set(EFFECTS) | set(TRIGGERS) | set(GAME_RULES) | set(INNOVATIONS)
        symbols |= {k for nodes in GAME_RULES.values() for k, _, v in nodes if isinstance(v, list) and k.startswith(PREFIX)}
        for f in (BASE / 'common').rglob('*.txt'):
            for k, op, v in walk(parse(f)):
                if k.startswith(PREFIX) and op and k not in INTERACTIONS and k not in SGUIS and k not in ON_ACTIONS:
                    self.assertIn(k, symbols | set(definitions('common/modifiers')) | set(definitions('common/script_values')), f)

    def test_high_skills_and_repeated_profiles(self):
        self.assertEqual(len(PROFILES), 120)
        for name in PROFILES:
            for base in (0, 30, 70, 100):
                with self.subTest(profile=name, base=base):
                    c = Character(base, {'loyal', 'scarred'}, monastic=True).run(name)
                    before = copy.deepcopy(c.__dict__)
                    c.run(name)
                    self.assertEqual(c.__dict__, before)
                    self.assertIn('loyal', c.traits)
                    self.assertIn('scarred', c.traits)
                    if 'stooge_' in name:
                        self.assertEqual(set(c.skills.values()), {0})
                        self.assertIn(PREFIX + 'valyrian_slave', c.modifiers)
                    else:
                        self.assertTrue(all(n >= base for n in c.skills.values()))

    def test_loyalty_and_eunuch_exceptions(self):
        for name, nodes in PROFILES.items():
            adds = [v for k, _, v in walk(nodes) if k == 'add_trait']
            self.assertNotIn('loyal', adds, name)
            if 'chief_eunuch_' not in name:
                self.assertNotIn('eunuch_1', adds, name)
                self.assertNotIn('beardless_eunuch', adds, name)
        c = Character(traits={'beardless_eunuch'}).run(PREFIX + 'prepare_chief_eunuch_court_position_effect')
        self.assertIn('beardless_eunuch', c.traits)
        self.assertNotIn('eunuch_1', c.traits)
        self.assertEqual(c.skills['intrigue'], 50)

    def test_status_traits_and_alternatives(self):
        almoner = PREFIX + 'prepare_high_almoner_court_position_effect'
        self.assertNotIn('devoted', Character().run(almoner).traits)
        self.assertIn('devoted', Character(monastic=True).run(almoner).traits)
        assassin = Character(traits={'honest', 'just', 'compassionate'}).run(PREFIX + 'prepare_master_assassin_court_position_effect')
        self.assertTrue({'murderer', 'order_member', 'faith_warrior'} <= assassin.traits)
        self.assertFalse({'honest', 'just', 'compassionate'} & assassin.traits)
        for role in ('gaoler_court_position', 'second_camp_officer'):
            effect = PREFIX + 'prepare_' + role + '_effect'
            self.assertEqual(Character().run(effect).traits & {'sadistic', 'callous'}, {'callous'})
            self.assertEqual(Character(traits={'sadistic'}).run(effect).traits & {'sadistic', 'callous'}, {'sadistic'})
        preceptor = Character().run(PREFIX + 'prepare_grand_preceptor_court_position_effect')
        self.assertTrue({'intellect_good_3', 'shrewd'} <= preceptor.traits)

    def test_languages_and_professional_experience(self):
        for role in ('travel_leader_court_position', 'cultural_emissary_court_position'):
            c = Character().run(PREFIX + 'prepare_' + role + '_effect')
            self.assertEqual(len(c.languages), 25)
            self.assertFalse({'language_agot_others', 'language_agot_children'} & c.languages)
        c = Character().run(PREFIX + 'prepare_travel_leader_court_position_effect')
        self.assertEqual(c.xp['lifestyle_traveler', 'travel'], 100)
        self.assertEqual(c.xp['lifestyle_traveler', 'danger'], 100)
        self.assertEqual(c.xp['lifestyle_hunter', 'hunter'], 100)
        self.assertNotIn(('lifestyle_hunter', 'falconer'), c.xp)
        smith = Character().run(PREFIX + 'prepare_court_smith_court_position_effect')
        self.assertIn('can_reforge_valyrian_steel', smith.flags)
        self.assertEqual(smith.skills['stewardship'], 60)
        self.assertEqual(smith.skills['prowess'], 60)

    def test_artificer_education_and_inspiration(self):
        c = Character().run(PREFIX + 'prepare_court_artificer_court_position_effect')
        self.assertEqual(set(c.skills.values()), {40})
        self.assertEqual(len({t for t in c.traits if t.startswith('education_')}), 1)
        nodes = PROFILES[PREFIX + 'prepare_court_artificer_court_position_effect']
        options = next(v for k, _, v in walk(nodes) if k == 'random_list')
        self.assertEqual(len(options), 5)
        self.assertFalse(any(k == 'create_inspiration' for k, _, v in walk(nodes)))
        spawn = EFFECTS[PREFIX + 'spawn_court_artificer_court_position_effect']
        self.assertTrue(any(k == 'type' and v == 'weapon_inspiration' for k, _, v in walk(spawn)))

    def test_education_preserves_absent_families(self):
        c = Character(traits={'education_martial_2', 'education_martial_prowess_1', 'education_heir_training_2', 'scarred'})
        c.run(PREFIX + 'education_effect')
        self.assertEqual(c.traits, {'education_martial_5', 'education_martial_prowess_5', 'education_heir_training_4', 'scarred'})
        previous = copy.deepcopy(c.__dict__)
        c.run(PREFIX + 'education_effect')
        self.assertEqual(c.__dict__, previous)

    def test_dragon_blood_boundaries(self):
        for female in (False, True):
            c = Character(traits={'dragon_spindly', 'dragon_slow', 'dragon_ugly', 'dragon_blind', 'dragon_physique_bad_3'}, female=female)
            c.run(PREFIX + 'dragon_enhancement_effect')
            self.assertTrue({'dragon_spindly', 'dragon_blind', 'dragon_physique_good_3', 'dragon_swift', 'dragon_majestic'} <= c.traits)
            self.assertFalse({'dragon_slow', 'dragon_ugly', 'dragon_physique_bad_3'} & c.traits)
            self.assertIn('inactive:dragon_fertile', c.flags)
            self.assertEqual('dragon_is_fertile' in c.variables, female)
        known = Character(traits={'dragon_fertile'}, female=True).run(PREFIX + 'dragon_enhancement_effect')
        self.assertIn('dragon_fertile', known.traits)
        self.assertNotIn('dragon_is_fertile', known.variables)

    def test_appointment_guards_and_exclusions(self):
        creations = {k: v for k, v in EFFECTS.items() if k.startswith(PREFIX + 'spawn_')}
        self.assertEqual(len(creations), 93)
        forbidden = ('warden_of_', 'white_knife_', 'stone_way_', 'princes_pass_', 'lorath_', 'goldcloaks_', 'b_')
        for name, nodes in creations.items():
            role = name.removeprefix(PREFIX + 'spawn_').removesuffix('_effect')
            self.assertFalse(role.startswith(forbidden), role)
            keys = [k for k, _, _ in walk(nodes)]
            self.assertIn('can_be_employed_as', keys, role)
            self.assertIn('appoint_court_position', keys, role)
            self.assertNotIn('revoke_court_position', keys, role)
            self.assertNotIn('replace_court_position', keys, role)
            self.assertTrue(any(k == 'add_trait' and v == 'loyal' for k, _, v in walk(nodes)), role)
            self.assertTrue(any(k == 'employer' and v == 'scope:' + PREFIX + 'employer' for k, _, v in walk(nodes)), role)
            for k, _, creation in walk(nodes):
                if k == 'create_character':
                    fields = [field_name for field_name, _, _ in creation]
                    self.assertEqual(len(fields), len(set(fields)), (role, 'duplicate creation property'))
                    self.assertEqual(field(creation, 'save_scope_as'), PREFIX + 'new_courtier')
        treatise_keys = [k for k, _, v in walk(EFFECTS[PREFIX + 'treatises_effect'])]
        self.assertNotIn('appoint_court_position', treatise_keys)
        self.assertIn('is_court_position_employer', treatise_keys)

    def test_trait_references_and_final_opposites_against_installation(self):
        game = Path('E:/SteamLibrary/steamapps/common/Crusader Kings III/game')
        agot = Path('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032')
        if not (agot / 'common/traits').exists():
            self.skipTest('Installed AGOT traits are unavailable')
        files = {}
        for root in (game, agot):
            for f in (root / 'common/traits').glob('*.txt'):
                files[f.name] = f
        traits = {k: v for f in files.values() for k, _, v in parse(f) if isinstance(v, list)}
        groups = {}
        for name, nodes in traits.items():
            group = field(nodes, 'group')
            if group:
                groups.setdefault(group, set()).add(name)
        for name, nodes in EFFECTS.items():
            for k, _, v in walk(nodes):
                if k in ('add_trait', 'remove_trait', 'make_trait_inactive'):
                    self.assertIn(v, traits, (name, k))
        for name in PROFILES:
            c = Character(monastic=True).run(name)
            for trait in c.traits:
                for other, _, _ in field(traits[trait], 'opposites', []):
                    candidates = {other} if other in traits else groups.get(other, set())
                    self.assertFalse(candidates & c.traits, (name, trait, other))


if __name__ == '__main__':
    unittest.main()
