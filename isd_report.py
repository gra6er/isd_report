from abc import ABC, abstractmethod
from dynaconf import Dynaconf
import argparse
from jira import JIRA
import sys
import pandas as pd


class Report:
    def __init__ (self, name, config):
        self.name = name
        self.timepoint_from = config.settings.timeframe.start
        self.timepoint_to = config.settings.timeframe.end

        self.params = []

        self.visual = None
        self.config = config

    def init_report_parameters(self):
        """
        Function that transform config ReportParameterN fileds to class objects
        """
        # TODO add ReportParams validation
        for report_parameter in self.config.settings.parameters.keys():
            self.params.append(getattr(sys.modules[__name__], report_parameter)(self.config)) 

    def count_parameters(self):
        for param in self.params:
            param.count()
        
        pass  


class ReportConfig:
    def __init__ (self, config_path):
        self.path = config_path
        self.settings = Dynaconf(envvar_prefix="DYNACONF", settings_files=config_path)
        # TODO validate settings
        self.sd = self.init_sd()
    

    def init_sd(self):
        """
        Initialize Jira SD
        """
        jira_url = self.settings.jira.url
        jira_user = self.settings.jira.username
        jira_password = self.settings.jira.password
        jira = JIRA(jira_url, basic_auth=(jira_user, jira_password))
        return jira


class ReportBuilder:
    def __init__(self, name = "report"):
        self.args = self.parse_args()
        self.config = ReportConfig(self.args.config.name)
        # TODO add rewriting config params by args params if exist
        self.report = Report(name=name, config=self.config)
        self.report.init_report_parameters()
        self.report.count_parameters()


    def parse_args(self):
        """
        Processing command line args
        """
        parser = argparse.ArgumentParser(description='Утилита создания отчётов')
        parser.add_argument('-c', '--config', required=True, type=argparse.FileType())
        args = parser.parse_args()
        return args

    def check_folders():
        """
        Checking system foldres for existing
        """
        pass

class ReportParameter(ABC):

    def __init__(self, config):
        self.value = None
        self.config = config

    @abstractmethod
    def count(self):
        pass

    # TODO join all parameters to map 
    def get_JQL(self, project = 'ISD', custom = None, assignee = None, created_from = None, created_to = None, issue_type = None, status = None):
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

    def get_none_incident_issues_JQL(self, timepoint_from, timepoint_to, breached = None):
        if breached == False: 
            return self.get_JQL(custom = '"Время до первого отклика" != breached()', created_from=timepoint_from, created_to=timepoint_to, issue_type='"Запрос на обслуживание", Изменение', status='Закрыта')
        else:
            return self.get_JQL(created_from=timepoint_from, created_to=timepoint_to, issue_type='"Запрос на обслуживание", Изменение', status='Закрыта')

    def get_incident_issues_JQL(self, timepoint_from, timepoint_to, breached = None):
        if breached == False: 
            return self.get_JQL(custom = '"Время на решение" != breached()', created_from=timepoint_from, created_to=timepoint_to, issue_type='Инцидент', status='Закрыта')
        else:
            return self.get_JQL(created_from=timepoint_from, created_to=timepoint_to, issue_type='Инцидент', status='Закрыта')


    def get_customfield_time(self, issue, customfield):
        # TODO write IndexError handling by finding reaction time in issue history
        try:
            time = issue.raw['fields'][customfield]['completedCycles'][0]['elapsedTime']['millis']
            return time
        except IndexError:
            raise

    def avg_customfield_time(self, issues, customfield):
        sum = 0
        for issue in issues:
            try:
                sum += self.get_customfield_time(issue, customfield)
            except:
                issues.total -= 1

        return sum / issues.total

class ReportParameter1(ReportParameter):

    def __init__(self, config):
        ReportParameter.__init__(self, config)
        

    def count(self):
        jira = self.config.sd
        timepoint_from = self.config.settings.timeframe.start
        timepoint_to = self.config.settings.timeframe.end

        issues = jira.search_issues(self.get_none_incident_issues_JQL(timepoint_from, timepoint_to, breached=False), maxResults=1)
        not_breached_count = issues.total
        issues = jira.search_issues(self.get_none_incident_issues_JQL(timepoint_from, timepoint_to), maxResults=1)
        all_count = issues.total

        self.value = not_breached_count / all_count * 100

    def __str__(self):
        return str(self.value)


class ReportParameter2(ReportParameter):

    def __init__(self, config):
        ReportParameter.__init__(self, config)

    def count(self):
        jira = self.config.sd
        timepoint_from = self.config.settings.timeframe.start
        timepoint_to = self.config.settings.timeframe.end

        issues = jira.search_issues(self.get_incident_issues_JQL(timepoint_from, timepoint_to, breached=False), maxResults=1)
        not_breached_count = issues.total
        issues = jira.search_issues(self.get_incident_issues_JQL(timepoint_from, timepoint_to), maxResults=1)
        all_count = issues.total

        self.value = not_breached_count / all_count * 100

    def __str__(self):
        return str(self.value)


class ReportParameter7(ReportParameter):

    def __init__(self, config):
        ReportParameter.__init__(self, config)

    def count(self):
        isd_members = self.config.settings.isd_members
        jira = self.config.sd
        timepoint_from = self.config.settings.timeframe.start
        timepoint_to = self.config.settings.timeframe.end

        df = pd.DataFrame(columns=["Инцидент (откл.)", "Инцидент (реш.)",  "Изменение", "Обслуживание"], index=isd_members)

        for member in isd_members:
            # TODO refactor this

            # Fill Инцидент (откл.) column
            incident_issues_10125 = jira.search_issues(self.get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='Инцидент', assignee=member) \
                , maxResults=False, fields=['customfield_10125'])

            incident_avg_time_10125  = self.avg_customfield_time(incident_issues_10125, 'customfield_10125')
            df.loc[member, 'Инцидент (откл.)'] = incident_avg_time_10125 / 60000

            # Fill Инцидент (реш.) column
            incident_issues_10401 = jira.search_issues(self.get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='Инцидент', assignee=member) \
                , maxResults=False, fields=['customfield_10401'])

            incident_avg_time_10401  = self.avg_customfield_time(incident_issues_10401, 'customfield_10401')
            df.loc[member, 'Инцидент (реш.)'] = incident_avg_time_10401 / 60000

            # Fill Изменение column
            change_issues = jira.search_issues(self.get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='Изменение', assignee=member) \
                , maxResults=False, fields=['customfield_10125'])

            change_avg_time  = self.avg_customfield_time(change_issues, 'customfield_10125')

            df.loc[member, 'Изменение'] = change_avg_time / 60000

            # Fill Обслуживание column
            service_issues = jira.search_issues(self.get_JQL(created_from=timepoint_from, created_to=timepoint_to, status='Закрыта', issue_type='"Запрос на обслуживание"', assignee=member) \
                , maxResults=False, fields=['customfield_10125'])

            service_avg_time  = self.avg_customfield_time(service_issues, 'customfield_10125')

            df.loc[member, 'Обслуживание'] = service_avg_time / 60000

        df = df.astype(float).round(2)
        self.value = df


class View(ABC):

    @abstractmethod
    def gen_view(self):
        pass


class RawView(View):

    def gen_view(self):
        pass


class PDFView(View):

    def gen_view(self):
        pass


if __name__ == '__main__':

    rb = ReportBuilder()
    for param in rb.report.params:
        print(str(param.value) + '\n')

    # rp1 = ReportParameter1('config')
    # print(rp1.get_none_incident_issues_JQL('2019-12-25 10:00', '2021-02-01', breached=False))
