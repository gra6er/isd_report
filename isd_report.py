from jira import JIRA
import pprint
import os

pp = pprint.PrettyPrinter(width=41, compact=True)

def print_issue(issue):
    """
    Print some issue fields
        Args:
            issue -- JIRA Issue object
    """

    pp.pprint(issue)
    pp.pprint('Создано: ' + issue.raw['fields']['created'])
    try:
        pp.pprint('Решено : ' + issue.raw['fields']['resolutiondate'])
    except:
        print('Решено : ')
    pp.pprint('Время до первого отклика (мс): ' + str(issue.raw['fields']['customfield_10125']['completedCycles'][0]['elapsedTime']['millis']))
    try:
        pp.pprint('Время на решение (мс): ' + str(issue.raw['fields']['customfield_10401']['completedCycles'][0]['elapsedTime']['millis']))
    except:
        print('Время на решение (мс): ')


def parameter_1(jira, timepoint_from, timepoint_to):
    """
    Count 1st reporting parameter: Share of timely processed requests
        Args:
            jira -- JIRA client object
            timepoint_from -- start timepoint of report timeframe 
            timepoint_to -- stop timepoint of report timeframe
        Return:
            int -- percentage of requests processed on time
    """

    # and type = Инцидент and priority = Безотлагательный

    issues = jira.search_issues(f'project = ISD and "Время до первого отклика" != breached() and created >= \'{timepoint_from}\' and created < \'{timepoint_to}\'', maxResults=1)
    not_breached_count = issues.total
    issues = jira.search_issues(f'project = ISD and created >= \'{timepoint_from}\' and created < \'{timepoint_to}\'', maxResults=1)
    all_count = issues.total

    print(f'1. not_breached: {not_breached_count}  all: {all_count}')

    return not_breached_count / all_count * 100


def parameter_2(jira, timepoint_from, timepoint_to):
    """
    Count 2st reporting parameter: Share of timely resolved requests
        Args:
            jira -- JIRA client object
            timepoint_from -- start timepoint of report timeframe 
            timepoint_to -- stop timepoint of report timeframe
        Return:
            int -- percentage of requests processed on time
    """

    # and type = Инцидент and priority = Безотлагательный

    issues = jira.search_issues(f'project = ISD and "Время на решение" != breached() and created >= \'{timepoint_from}\' and created < \'{timepoint_to}\'', maxResults=1)
    not_breached_count = issues.total
    issues = jira.search_issues(f'project = ISD and created >= \'{timepoint_from}\' and created < \'{timepoint_to}\'', maxResults=1)
    all_count = issues.total

    print(f'2. not_breached: {not_breached_count}  all: {all_count}')

    return not_breached_count / all_count * 100

def parameter_7(jira, timepoint_from, timepoint_to):
    """
    Count 3st reporting parameter: Average processing time for requests of various categories
        Args:
            jira -- JIRA client object
            timepoint_from -- start timepoint of report timeframe 
            timepoint_to -- stop timepoint of report timeframe
        Return:
            int -- percentage of requests processed on time
    """
    issues = jira.search_issues(f'project = ISD and status = Закрыта and created >= \'{timepoint_from}\' and created < \'{timepoint_to}\'', maxResults=False, fields=['customfield_10125', 'customfield_10401'])

    print(len(issues))

    # TODO Узнать как это обрабатывать
    # ---------------------------------

    total = issues.total
    total_10125 = total
    total_10401 = total
    millis_sum_10125 = 0
    millis_sum_10401 = 0
    excluded_count_10125 = 0
    excluded_count_10401 = 0
    for issue in issues:
        if len(issue.raw['fields']['customfield_10125']['completedCycles']) == 0:
            total_10125 -= 1
            excluded_count_10125 += 1  
        else:
            millis_sum_10125 += issue.raw['fields']['customfield_10125']['completedCycles'][0]['elapsedTime']['millis']
    
        if len(issue.raw['fields']['customfield_10401']['completedCycles']) == 0:
                total_10401 -= 1
                excluded_count_10401 += 1
        else:
            millis_sum_10401 += issue.raw['fields']['customfield_10401']['completedCycles'][0]['elapsedTime']['millis']
    

    print(f"Excluded count (10125): {excluded_count_10125}")
    print(f"Excluded count (10401): {excluded_count_10401}")

    millis_mean_10125 = millis_sum_10125 / total_10125
    millis_mean_10401 = millis_sum_10401 / total_10401
    return (millis_mean_10125, millis_sum_10401)


jira_host = os.getenv('JIRA_URL')
jira_user = os.getenv('JIRA_USER')
jira_password = os.getenv('JIRA_PASSWORD')

jira = JIRA(jira_host, basic_auth=(jira_user, jira_password))

timepoint_from = os.getenv('TIMEPOINT_FROM')
timepoint_to = os.getenv('TIMEPOINT_TO')

# print(parameter_1(jira, timepoint_from, timepoint_to))
# print(parameter_2(jira, timepoint_from, timepoint_to))
print(parameter_7(jira, timepoint_from, timepoint_to))

