"""Record user-approved exceptions and expected changes against the old log."""
import collections
import csv
import json
from pathlib import Path
import sys
import Build as b

sys.stdout.reconfigure(encoding='utf-8')
SOURCE=b.REPO/'docs/reports/scripts-variables-analysis-2026-09-19/diagnostic-inventory.csv'
FIXED={
 'core-sword-recognition','di-lhazar-language','di-personalities','di-polyglot',
 'lotd-sword-templates','lotd-scheme-bonus','lotd-ruby-gold','lotd-baelor-marker',
 'lotd-maekar-selection','lotd-unused-sword-markers','cow-holding-trigger','cow-map-mode','cow-quarries',
 'crowns-culture-opinion','crowns-shattered-rule','crowns-event-duplicate','crowns-myrcella',
 'crowns-baldric','crowns-roland-uniqueness','bookmarked-april-scenario','vs-egg-colors','vs-scheme-formats',
 'localization-decision','localization-religion-family'}
EXCEPTIONS={
 'core-house-scope':'Интеграция TGC сохранена целиком по указанию пользователя; известная опечатка в неактивной ветви также оставлена.',
 'core-obsolete-cloak-gate':'Интеграционный блок Core сохранён; не включать отсутствующий старый шаблон плаща.',
 'core-optional-armor':'Отсутствующая необязательная интеграция AOTK; код и правила не подменять.',
 'core-optional-tgc':'Отсутствующая необязательная интеграция TGC; код и правила не подменять.',
 'core-optional-markers':'Маркеры предусмотренных внешних интеграций Core сохранены.',
 'di-confucian-xp':'Исходный Divine Intervention для ванили не исправляется по указанию пользователя.',
 'di-faith-families':'Исходный Divine Intervention для ванили не исправляется по указанию пользователя.',
 'di-persian-marriage':'Исходный Divine Intervention для ванили не исправляется по указанию пользователя.',
 'di-succession-innovation':'Исходный Divine Intervention для ванили не исправляется по указанию пользователя.',
 'di-varangian':'Исходный Divine Intervention для ванили не исправляется по указанию пользователя.',
 'di-gui-artifact-origin':'Действительное использование GUI / резервным вариантом выбора.',
 'di-gui-display':'Переменные читаются интерфейсом и локализацией.',
 'di-gui-holdings':'MakeScopeFlag из GUI устанавливает значения; сохранить кнопки.',
 'lotd-empty-result':'Значение all_found очищает предыдущий выбор предмета; сохранить.',
 'cow-integration-marker':'Сохранить публичный маркер наличия COW для совместимости.'}
DEFERRED={
 'shared-crown-creator':'CREATOR в AGOT+ и LOTD оставлен для следующего этапа.',
 'cow-missing-event':'Утраченное событие COW: отдельное исследование, вызовы сохранены.',
 'cow-religion-opinion':'Прежний охват религиозного бонуса не определён; сохранено до отдельного этапа.'}


def main():
    rows=list(csv.DictReader(SOURCE.open(encoding='utf-8-sig',newline='')))
    output=[]
    for r in rows:
        issue=r['issue']
        if issue in FIXED:status='expected_fixed';reason='Исправлено статически; исчезновение сообщения ещё не подтверждено запуском.'
        elif issue in EXCEPTIONS:status='exception';reason=EXCEPTIONS[issue]
        elif issue in DEFERRED:status='deferred';reason=DEFERRED[issue]
        elif issue=='cow-building-ids':
            if "'harlaw_mines_01'" in r['message'] or 'line: 335 ' in r['message']:
                status='deferred';reason='Неизвестный преемник шахт Харлоу; исходная ветвь сохранена.'
            else:status='expected_fixed';reason='Исправлены подтверждённые ID порта/Медвежьего острова и старое бессильное удаление ironwood_01.'
        else:raise AssertionError(issue)
        output.append(dict(r,status=status,reason=reason))
    totals=dict(collections.Counter(x['status'] for x in output))
    assert len(output)==264 and totals['expected_fixed']==103,totals
    with (b.MOD/'docs/diagnostic-disposition.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(output[0]),lineterminator='\n');writer.writeheader();writer.writerows(output)
    bymod={}
    for x in output:
        bymod.setdefault(x['owner'],collections.Counter())[x['status']]+=1
    result=dict(reference_log_diagnostics=264,status_counts=totals,by_mod=bymod,
                rule='Exceptions are documentation only; error.log and engine validation are not filtered or disabled.',
                runtime_verified=False)
    (b.MOD/'docs/expected-log.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
