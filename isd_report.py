from abc import ABC, abstractmethod
from dynaconf import Dynaconf
import argparse
from jira import JIRA
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt


class Report:
    def __init__ (self, name, config):
        self.name = name or f"report_{datetime.now().strftime('%Y_%m_%d__%H-%M-%S')}"
        self.config = config
        self.report_dir_path = ''
        self.timepoint_from = self.config.settings.timeframe.start
        self.timepoint_to = self.config.settings.timeframe.end

        self.params = []

        self.visual = None

    def init_report_parameters(self):
        """
        Function that transform config ReportParameterN fileds to class objects
        """
        # TODO add ReportParams validation
        for report_parameter in self.config.settings.parameters.keys():
            self.params.append(getattr(sys.modules[__name__], report_parameter)(self.config, self.report_dir_path)) 

    def create_report_instance_folder(self):
        report_folder = Path(self.config.settings.reports_dir.path, 'reports/')
        report_folder = report_folder / Path(self.name)

        if not report_folder.exists():
            print(f"[INFO]  Creating report instance folder: {self.name}")
            report_folder.mkdir(parents=True, exist_ok=True) 
        else:
            print(f"[ERROR] Report instance folder witn name {self.name} already exists")
            exit()

        self.report_dir_path = report_folder

    def count_parameters(self):
        for param in self.params:
            param.count()

    def gen_rp_output(self):
        for param in self.params:
            param.generate_output()

    def gen_rp_view(self):
        for param in self.params:
            param.init_view()
            param.view.gen_view()
        


class ReportConfig:
    def __init__ (self, config_path):
        self.config_path = config_path
        self.settings = Dynaconf(envvar_prefix="DYNACONF", settings_files=config_path)
        self.reports_dir = self.settings.reports_dir.path
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
    def __init__(self, name = f"report_{datetime.now().strftime('%Y_%m_%d__%H-%M-%S')}"):
        self.args = self.parse_args()
        # TODO add rewriting config params by args params if exist
        self.report = Report(name=name, config=ReportConfig(self.args.config.name))
        self.config = self.report.config
        self.check_reports_folder()
        self.report.create_report_instance_folder()
        self.report.init_report_parameters()
        self.report.count_parameters()
        self.report.gen_rp_output()
        self.report.gen_rp_view()


    def parse_args(self):
        """
        Processing command line args
        """
        parser = argparse.ArgumentParser(description='Утилита создания отчётов')
        parser.add_argument('-c', '--config', required=True, type=argparse.FileType())
        args = parser.parse_args()
        return args

    def check_reports_folder(self):
        """
        Check reports folder exists
        If not exists - create it 
        """
        reports_path = Path(self.config.settings.reports_dir.path)
        reports_path = reports_path / Path('reports/')

        if not reports_path.exists():
            print("[INFO]  Creating reports folder")
            reports_path.mkdir(parents=True, exist_ok=True) 
        else:
            print("[INFO]  Reports folder exists")

class ReportParameter(ABC):

    def __init__(self, config, report_dir_path, rp_type):
        self.value = None
        self.rp_type = rp_type
        self.config = config
        self.rp_info = {
            'header': '',
            'description': '',
            'caption': '',
            'comment': '',
        }
        self.report_dir_path = report_dir_path
        self.create_parameter_folder()

    @abstractmethod
    def count(self):
        pass

    def create_parameter_folder(self):
        parameter_folder = Path(self.report_dir_path, self.__class__.__name__)
        parameter_folder.mkdir(parents=True, exist_ok=True)
        self.parameter_dir_path = parameter_folder
        print(f"[INFO]  Creating parameter folder for: {self.__class__.__name__}")
        pass

    def generate_output(self):
        
        if self.rp_type == 'value':
            print(f"[INFO]  Generating output for: {self.__class__.__name__}")
            self.parameter_value_path = Path(self.parameter_dir_path, 'value.txt')
            with self.parameter_value_path.open('w', encoding='utf-8', ) as f:
                f.write(str(self.value))
        elif self.rp_type == 'table':
            print(f"[INFO]  Generating output for: {self.__class__.__name__}")
            self.parameter_value_path = Path(self.parameter_dir_path, 'value.csv')
            # TODO create encoding fields to RP class
            self.value.to_csv(self.parameter_value_path, sep=';', encoding='cp1251')
        else:
            print(f"[ERROR] Unknown report parameter type for: {self.__class__.__name__}. Must be value or table.")            


    def init_view(self):
        template_dir_path = self.config.settings.template_dir_path or Path("./templates")
        if self.rp_type == 'value':
            self.view = ValueView(self.parameter_dir_path, template_dir_path, self.rp_info, self.value)
        elif self.rp_type == 'table':
            self.view = TableView(self.parameter_dir_path, template_dir_path, self.rp_info, self.value)
        else:
            print(f"[ERROR] Unknown report parameter type for: {self.__class__.__name__}. Must be value or table.")            



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

    def __init__(self, config, report_dir_path, ):
        ReportParameter.__init__(self, config, report_dir_path, "value")
        self.rp_info = {
            'header': self.config.settings.parameters.ReportParameter1.header,
            'description': self.config.settings.parameters.ReportParameter1.description,
            'caption': self.config.settings.parameters.ReportParameter1.caption,
            'comment': self.config.settings.parameters.ReportParameter1.comment,
        }
        

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

    def __init__(self, config, report_dir_path):
        ReportParameter.__init__(self, config, report_dir_path, "value")
        self.rp_info = {
            'header': self.config.settings.parameters.ReportParameter2.header,
            'description': self.config.settings.parameters.ReportParameter2.description,
            'caption': self.config.settings.parameters.ReportParameter2.caption,
            'comment': self.config.settings.parameters.ReportParameter2.comment,
        }
        

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

    def __init__(self, config, report_dir_path):
        ReportParameter.__init__(self, config, report_dir_path, "table")
        self.rp_info = {
            'header': self.config.settings.parameters.ReportParameter7.header,
            'description': self.config.settings.parameters.ReportParameter7.description,
            'caption': self.config.settings.parameters.ReportParameter7.caption,
            'comment': self.config.settings.parameters.ReportParameter7.comment,
        }

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

    def __init__(self, parameter_dir_path, template_dir_path, rp_info, value):
        self.parameter_dir_path = parameter_dir_path
        self.rp_info = rp_info
        self.value = value
        self.template_dir_path = template_dir_path
        self.create_parts_folder()

    @abstractmethod
    def gen_view(self):
        pass

    def create_parts_folder(self):
        self.part_dir_path = Path(self.parameter_dir_path, 'parts')
        self.part_dir_path.mkdir(parents=True, exist_ok=True)


class ValueView(View):

    def __init__(self, parameter_dir_path, rp_info, value): 
        View.__init__(self, parameter_dir_path, rp_info, value)


    def gen_view(self):
        self.create_img_folder()
        self.gen_pie_img(self.value, Path(self.img_dir_path, 'pie.png'))


    def create_img_folder(self):
        self.img_dir_path = Path(self.part_dir_path, 'img')
        self.img_dir_path.mkdir(parents=True, exist_ok=True)


    def gen_pie_img(self, amount, filename):
        vals = [amount, 100 - amount]
        labels = [str(round(x, 2)) for x in vals]
        colors = ['green', 'red']
        explode = (0.1, 0)

        fig, ax = plt.subplots()
        ax.pie(vals, labels=labels, colors=colors, explode=explode, startangle=90)
        fig.savefig(filename)


class TableView(View):

    def __init__(self, parameter_dir_path, rp_info, value): 
        View.__init__(self, parameter_dir_path, rp_info, value)

    def gen_view(self):
        self.create_html_folder()
        self.gen_html_table()
    
    def gen_html_table(self):
        html = self.value.to_html()
        self.html_table_path = Path(self.html_dir_path, "table.html")
        with self.html_table_path.open('w', encoding='utf-8', ) as f:
                f.write(html)

    def create_html_folder(self):
        self.html_dir_path = Path(self.part_dir_path, 'html')
        self.html_dir_path.mkdir(parents=True, exist_ok=True)



if __name__ == '__main__':

    rb = ReportBuilder()
    for param in rb.report.params:
        print(str(param.value) + '\n')

    # rp1 = ReportParameter1('config')
    # print(rp1.get_none_incident_issues_JQL('2019-12-25 10:00', '2021-02-01', breached=False))
