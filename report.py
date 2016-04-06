"""Simple, sample script for generating a markdown report."""

from collections import defaultdict
from jira import JIRA
from os import environ
from sys import argv

# Get JIRA configs
options = {'server': environ['JIRA_DOMAIN']}
username = environ['JIRA_USERNAME']
password = environ['JIRA_PASSWORD']

# Authenticate with JIRA
j = JIRA(options, basic_auth=(username, password))

SPRINT_ID = argv[1] if len(argv) > 2 else 275

TICKETS = {
    'added': 'issueKeysAddedDuringSprint',
    'completed': 'completedIssues',
    'punted': 'puntedIssues',
    'incompleted': 'issuesNotCompletedInCurrentSprint'
}

SUMS = {
    'completed': 'completedIssuesEstimateSum',
    'punted': 'puntedIssuesEstimateSum',
    'incompleted': 'issuesNotCompletedEstimateSum',
}


def sprint_request(url, sid):
    """Return sprint data for given URL."""
    url = '{}?sprintId={}'.format(url, sid)
    return j._get_json(url, base=j.AGILE_BASE_URL)


def create_line(index, issue, domain):
    """Create markdown syntax line for report."""
    line = '{0}.\t[{1}]({2}/browse/{1}) {3} - {4}\n'
    return line.format(
        index,
        issue.key,
        domain,
        issue.fields.summary,
        int(issue.fields.customfield_11302)
    )

###############################################################################
# Start constructing report with ticket numbers and story point sums
###############################################################################

# This endpoint has all the interesting info
sprint = sprint_request('rapid/charts/sprintreport', SPRINT_ID)
sprint_info = sprint['contents']
report = defaultdict(dict)

# Get all the ticket numbers
for key, value in TICKETS.iteritems():
    if isinstance(sprint_info[value], dict):
        # The JIRA API is inconsistent
        report[key]['tickets'] = set(sprint_info[value].keys())
    else:
        # 'key' is the key JIRA uses for accessing ticket numbers
        report[key]['tickets'] = set(i.get('key') for i in sprint_info[value])

# The planned tickets are the union of all tickets minus the added ones
all_ticket_numbers = set.union(*(v['tickets'] for v in report.values()))
report['planned']['tickets'] = all_ticket_numbers - report['added']['tickets']

# Get all the ticket story point sums
for key, value in SUMS.iteritems():
    report[key]['sum'] = int(sprint_info[value].get('value', 0))


###############################################################################
# Construct strings and sum some story points
###############################################################################

# Get all tickets by their ticket number
tickets = list(j.search_issues(
    'issueKey in ({})'.format(','.join(all_ticket_numbers))
))

# This part is not pretty, it's pretty repetitive and hard to read
report['planned']['sum'] = 0
report['added']['sum'] = 0
for k, v in report.iteritems():
    report[k]['text'] = ''
for t in tickets:
    # 11302 is the id of our Story Points custom field
    story_points = t.fields.customfield_11302
    if t.key in report['planned']['tickets']:
        idx = report['planned'].get('text', '').count('\n') + 1
        report['planned']['text'] += create_line(idx, t, options['server'])
        # Worth noting is that this number may be wrong if any of the planned
        # tickets were resized during the sprint. The calculations for this
        # can kind of tricky, so they're omitted from this script
        report['planned']['sum'] += story_points
    if t.key in report['added']['tickets']:
        idx = report['added'].get('text', '').count('\n') + 1
        report['added']['text'] += create_line(idx, t, options['server'])
        report['added']['sum'] += story_points
    if t.key in report['completed']['tickets']:
        idx = report['completed'].get('text', '').count('\n') + 1
        report['completed']['text'] += create_line(idx, t, options['server'])
    if t.key in report['punted']['tickets']:
        idx = report['punted'].get('text', '').count('\n') + 1
        report['punted']['text'] += create_line(idx, t, options['server'])
    if t.key in report['incompleted']['tickets']:
        idx = report['incompleted'].get('text', '').count('\n') + 1
        report['incompleted']['text'] += create_line(idx, t, options['server'])

###############################################################################
# Generate the report
###############################################################################
planned_sum = report['planned']['sum']
completed_sum = report['completed']['sum']
incompleted_sum = report['incompleted']['sum']
planned_tix = len(report['planned']['tickets'])
completed_tix = len(report['completed']['tickets'])
added_tix = len(report['added']['tickets'])
print("""
### Committed
{}
### Completed
{}
***

### Added
{}
### Punted
{}
### Incompleted
{}
***

### Stats
- Points Committed: **{}**
- Points Completed: **{}**
- Points Incomplete: **{}**
- Percent of Committed Points: **{:.2%}**
- Percent of Committed Tickets: **{:.2%}**
- Percent of Committed Tickets' Points: **{:.2%}**
""".format(
    report['planned']['text'],
    report['completed']['text'],
    report['added']['text'],
    report['punted']['text'],
    report['incompleted']['text'],
    int(planned_sum),
    int(completed_sum),
    int(incompleted_sum),
    completed_sum / planned_sum,
    float(completed_tix - added_tix) / planned_tix,
    (planned_sum - incompleted_sum) / planned_sum,
))
