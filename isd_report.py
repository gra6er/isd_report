from io import StringIO
from jira import JIRA
import pprint
import pandas as pd
import argparse
from dynaconf import Dynaconf
import matplotlib.pyplot as plt
import os
from jinja2 import Template
import pdfkit


DATA_FOLDER = ".data/"
PARTS_FOLDER = f"{DATA_FOLDER}parts/"
TEMPLATE_FOLDER = 'templates/'
HTML_FOLDER = f"{DATA_FOLDER}html/"

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

# TODO join all parameters to map 
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

    # TODO logging
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
    issues = jira.search_issues(get_incident_issues_JQL(timepoint_from, timepoint_to, breached=False), maxResults=1)
    not_breached_count = issues.total
    issues = jira.search_issues(get_incident_issues_JQL(timepoint_from, timepoint_to), maxResults=1)
    all_count = issues.total

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

    df = df.astype(float).round(2)
    return df


def gen_pie_img(amount, filename):
    vals = [amount, 100 - amount]
    labels = [str(round(x, 2)) for x in vals]
    colors = ['green', 'red']
    explode = (0.1, 0)

    fig, ax = plt.subplots()
    ax.pie(vals, labels=labels, colors=colors, explode=explode, startangle=90)
    fig.savefig(filename)


def gen_tablefile_for_p7(df, filename):
    html = df.to_html()

    #write html to file
    text_file = open(PARTS_FOLDER + filename, "w", encoding='utf-8')
    text_file.write(html)
    text_file.close()


def gen_html_from_temlate(tmpl_file, output_file, context):
    template = Template(open(TEMPLATE_FOLDER + tmpl_file, 'r', encoding='utf-8').read())
    output_html = open(HTML_FOLDER + output_file, "w", encoding='utf-8')
    output_html.write(template.render(context))
    output_html.close()


def join_htmls(filename, tmpl_file):
    htmls_list = os.listdir(HTML_FOLDER)
    html_content = ''

    for item in htmls_list:
        html_content += open(HTML_FOLDER + item, 'r', encoding='utf-8').read()
    
    template = Template(open(TEMPLATE_FOLDER + tmpl_file, 'r', encoding='utf-8').read())
    output_html = open(HTML_FOLDER + filename, "w", encoding='utf-8')
    output_html.write(template.render(content=html_content))
    output_html.close()


def generate_pdf(html_file, pdf_file):
   pdfkit.from_file(html_file, pdf_file)


def remove_folder_content(path):
    """
    Removing content of the folder (files only)
    """
    for root, dirs, files in os.walk(path):
        for file in files:
            os.remove(root + '/' + file)


# MAIN
#------

# Processing command line args
parser = argparse.ArgumentParser(description='Утилита создания отчётов')
parser.add_argument('-c', '--config', required=True, type=argparse.FileType())
args = parser.parse_args()

# Reading config
settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=[args.config.name],
)

# Setting up Jira connection
jira_url = settings.jira.url
jira_user = settings.jira.username
jira_password = settings.jira.password

jira = JIRA(jira_url, basic_auth=(jira_user, jira_password))

# Getting timepoints from config
timepoint_from = settings.timeframe.start
timepoint_to = settings.timeframe.end

# Check service folders exists or not

for folder in [DATA_FOLDER, PARTS_FOLDER, HTML_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
    else:
        remove_folder_content(folder)

# Setting context and generating parameter's 1 value, imgs and html

header = '1. Доля своевременно обработанных запросов'
desc = 'SLA - Время до первого отклика'
footer = 'в %'
page = ""
img_filename = PARTS_FOLDER + 'parameter1.png'

context = {'header': header, 'desc': desc, 'footer': footer, 'page': page, 'img_filename': img_filename}

print(f"{header} ({footer}):")
p1 = parameter_1(jira, timepoint_from, timepoint_to)
print(p1)
gen_pie_img(p1, img_filename)
gen_html_from_temlate('pie_tmpl.html.j2', 'p1.html', context=context)

# Setting context and generating parameter's 2 value, imgs and html

header = '2. Доля своевременно решенных запросов'
desc = 'SLA - Время до решения'
footer = 'в %'
page = "new-page"
img_filename = PARTS_FOLDER + 'parameter2.png'

context = {'header': header, 'desc': desc, 'footer': footer, 'page': page, 'img_filename': img_filename}

print(f"{header} ({footer}):")
p2 = parameter_2(jira, timepoint_from, timepoint_to)
print(p2)
gen_pie_img(p2, img_filename)
gen_html_from_temlate('pie_tmpl.html.j2', 'p2.html', context=context)

# Setting context and generating parameter's 7 table and html

# TODO join imf_filename and table to field content and join templates
header = '7. Среднее время обработки запросов различных типов заявок'
desc = 'В зависимости от работника:'
footer = 'в минутах'
page = "new-page"

print(f"{header} ({footer}):")
p7 = parameter_7(jira, timepoint_from, timepoint_to)
print(p7)

gen_tablefile_for_p7(p7, 'parameter7.html')
table = open(PARTS_FOLDER + 'parameter7.html', 'r', encoding='utf-8').read()

context = {'header': header, 'desc': desc, 'footer': footer, 'page': page, 'table': table}

gen_html_from_temlate('table_tmpl.html.j2', 'p7.html', context=context)

# Join html parts to one big html using template 

join_htmls('report.html', 'report_tmpl.html.j2')

# Convert html to pdf

generate_pdf(HTML_FOLDER + 'report.html', 'report.pdf')
