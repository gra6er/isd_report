from jira import JIRA
import pprint
import pandas as pd
import argparse
from dynaconf import Dynaconf
import matplotlib.pyplot as plt


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


def get_JQL(project = 'ISD', custom = None, assignee = None, created_from = None, created_to = None, issue_type = None, status = None):
    jql = 'project = ' + project
    if custom is not None:
        jql += f' and {custom}'
    if status is not None:
        jql += f' and status in({status})'
    if assignee is not None:
        jql += f' and assignee in({assignee})'
    if created_from is not None:
        jql += f' and created >= "{created_from}"'
    if created_to is not None:
        jql += f' and created <= "{created_to}"'
    if issue_type is not None:
        jql += f' and issuetype in({issue_type})'

    return jql


def get_incident_issues_JQL(timepoint_from, timepoint_to, breached = None):
    if breached == False: 
        return get_JQL(custom = '"Время на решение" != breached()', created_from=timepoint_from, created_to=timepoint_to, issue_type='Инцидент', status='Закрыта')
    else:
        return get_JQL(created_from=timepoint_from, created_to=timepoint_to, issue_type='Инцидент', status='Закрыта')


def get_none_incident_issues_JQL(timepoint_from, timepoint_to, breached = None):
    if breached == False: 
        return get_JQL(custom = '"Время до первого отклика" != breached()', created_from=timepoint_from, created_to=timepoint_to, issue_type='"Запрос на обслуживание с заверениями", Изменение', status='Закрыта')
    else:
        return get_JQL(created_from=timepoint_from, created_to=timepoint_to, issue_type='"Запрос на обслуживание с заверениями", Изменение', status='Закрыта')


def get_customfield_time(issue, customfield):
    # TODO write IndexError handling by finding reaction time in issue history
    try:
        time = issue.raw['fields'][customfield]['completedCycles'][0]['elapsedTime']['millis']
        return time
    except IndexError:
        raise

def avg_customfield_time(issues, customfield):
    sum = 0
    for issue in issues:
        try:
            sum += get_customfield_time(issue, customfield)
        except:
            issues.total -= 1
   
    return sum / issues.total

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

    issues = jira.search_issues(get_none_incident_issues_JQL(timepoint_from, timepoint_to, breached=False), maxResults=1)
    not_breached_count = issues.total
    issues = jira.search_issues(get_none_incident_issues_JQL(timepoint_from, timepoint_to), maxResults=1)
    all_count = issues.total

    # print(f'1. not_breached: {not_breached_count}  all: {all_count}')

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

    issues = jira.search_issues(get_incident_issues_JQL(timepoint_from, timepoint_to, breached=False), maxResults=1)
    not_breached_count = issues.total
    issues = jira.search_issues(get_incident_issues_JQL(timepoint_from, timepoint_to), maxResults=1)
    all_count = issues.total

    # print(f'2. not_breached: {not_breached_count}  all: {all_count}')

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
    # start_time = datetime.now()

    isd_members = settings.isd_members

    df = pd.DataFrame(columns=["Инцидент (откл.)", "Инцидент (реш.)",  "Изменение", "Обслуживание"], index=isd_members)

    for member in isd_members:
        # TODO refactor this

        # Fill Инцидент (откл.) column
        incident_issues_10125 = jira.search_issues(get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='Инцидент', assignee=member) \
            , maxResults=False, fields=['customfield_10125']) 

        incident_avg_time_10125  = avg_customfield_time(incident_issues_10125, 'customfield_10125')
        df.loc[member, 'Инцидент (откл.)'] = incident_avg_time_10125 / 60000

        # Fill Инцидент (реш.) column
        incident_issues_10401 = jira.search_issues(get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='Инцидент', assignee=member) \
            , maxResults=False, fields=['customfield_10401'])

        incident_avg_time_10401  = avg_customfield_time(incident_issues_10401, 'customfield_10401')
        df.loc[member, 'Инцидент (реш.)'] = incident_avg_time_10401 / 60000

        # Fill Изменение column
        change_issues = jira.search_issues(get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='Изменение', assignee=member) \
            , maxResults=False, fields=['customfield_10125'])

        change_avg_time  = avg_customfield_time(change_issues, 'customfield_10125')

        df.loc[member, 'Изменение'] = change_avg_time / 60000

        # Fill Обслуживание column
        service_issues = jira.search_issues(get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='"Запрос на обслуживание с заверениями"', assignee=member) \
            , maxResults=False, fields=['customfield_10125'])

        service_avg_time  = avg_customfield_time(service_issues, 'customfield_10125')

        df.loc[member, 'Обслуживание'] = service_avg_time / 60000
        
    # print(f'\n time for 7 param: {datetime.now() - start_time}')

    df = df.astype(float).round(2)
    return df

def pie_visualize_parameter(amount):
    vals = [amount, 100 - amount]
    labels = [str(round(x, 2)) for x in vals]
    colors = ['green', 'red']
    explode = (0.1, 0)

    fig, ax = plt.subplots()
    ax.pie(vals, labels=labels, colors=colors, explode=explode, startangle=90)
    fig.savefig('my_plot.png')

def visualize_parameter7(df):
    html = df.to_html()

    #write html to file
    text_file = open("index.html", "w")
    text_file.write(html)
    text_file.close()

parser = argparse.ArgumentParser(description='Утилита создания отчётов')
parser.add_argument('-c', '--config', required=True, type=argparse.FileType())
args = parser.parse_args()

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=[args.config.name],
)

jira_url = settings.jira.url
jira_user = settings.jira.username
jira_password = settings.jira.password

jira = JIRA(jira_url, basic_auth=(jira_user, jira_password))

timepoint_from = settings.timeframe.start
timepoint_to = settings.timeframe.end

print("1. Доля своевременно обработанных запросов (в %):")
p1 = parameter_1(jira, timepoint_from, timepoint_to)
print(p1)
pie_visualize_parameter(p1)

print("\n2. Доля своевременно решенных запросов (в %):")
p2 = parameter_2(jira, timepoint_from, timepoint_to)
print(p2)
pie_visualize_parameter(p2)

print("\n7. Среднее время обработки запросов различных типов заявок (в минутах):")
p7 = parameter_7(jira, timepoint_from, timepoint_to)
print(p7)
visualize_parameter7(p7)


# print(get_JQL(custom = '"Время до первого отклика" != breached()', created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='"Запрос на обслуживание с заверениями", Изменение', assignee=", ".join(isd_members)))
