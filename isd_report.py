from jira import JIRA
import pprint
import os

pp = pprint.PrettyPrinter(width=41, compact=True)

jira_host = os.getenv('JIRA_URL')
jira_user = os.getenv('JIRA_USER')
jira_password = os.getenv('JIRA_PASSWORD')


jira = JIRA(jira_host, basic_auth=(jira_user, jira_password))

timepoint_from = '2019-12-25 10:00'
timepoint_to = '2020-02-01'

issues = jira.search_issues(f'project = ISD and type = Инцидент and priority = Безотлагательный and created >= \'{timepoint_from}\' and created < \'{timepoint_to}\'')

for item in issues:
    pp.pprint(item)
    pp.pprint('Создано: ' + item.raw['fields']['created'])
    pp.pprint('Решено : ' + item.raw['fields']['resolutiondate'])
    pp.pprint('Время до первого отклика (мс): ' + str(item.raw['fields']['customfield_10125']['completedCycles'][0]['elapsedTime']['millis']))
    pp.pprint('Время на решение (мс): ' + str(item.raw['fields']['customfield_10401']['completedCycles'][0]['elapsedTime']['millis']))
    print('-' * 10)