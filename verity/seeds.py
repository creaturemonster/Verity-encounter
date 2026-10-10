"""Fictional teaching fixtures. No patient records; no clinical validation."""
import copy


def fact(fid, label, answer, aliases=(), group='History', disclosure='ask', **extra):
    return dict(id=fid, label=label, answer=answer, aliases=list(aliases), group=group,
                disclosure=disclosure, requires=[], requires_empathy=False,
                attachment_ids=[], **extra)


def objective(oid, title, fids=(), signal='', critical=False, weight=1):
    return dict(id=oid, title=title, fact_ids=list(fids), signal=signal, critical=critical, weight=weight)


def cases():
    a = {
        'title': 'A change in energy', 'setting': 'Outpatient interview',
        'description': 'Explore a new symptom, medication history and an everyday barrier to follow-up.',
        'author': 'Verity synthetic demo fixture', 'synthetic': True,
        'patient': {'name': 'Jordan Avery', 'age': 42, 'pronouns': 'they/them'},
        'facts': [
            fact('opening', 'Presenting concern', 'I have been feeling unusually tired, and it is starting to affect my day.', group='Presenting concern', disclosure='initial'),
            fact('onset', 'Onset and course', 'It started about three weeks ago. It has been happening most days.', ['when did','how long','started','onset','when it began']),
            fact('impact', 'Impact on daily life', 'I used to walk home without stopping. Now I often stop to rest halfway.', ['affected','daily life','impact','what brings','tell me more','tell me about','walk me through']),
            fact('associated', 'Associated symptoms', 'I sometimes feel lightheaded when I stand up quickly. I have not had chest pain or a fever.', ['other symptoms','lightheaded','dizzy','chest pain','fever','anything else']),
            fact('medications', 'Medicines and supplements', 'I take cetirizine for seasonal allergies. I am not taking any supplements.', ['medications','medicines','medicine','medication','supplements','taking','tablets']),
            fact('allergies', 'Reported allergy history', 'I developed an itchy rash after taking penicillin when I was a teenager.', ['allergies','allergic','drug reactions','penicillin']),
            fact('sleep', 'Sleep and schedule', 'I started working nights a month ago. I usually sleep four or five hours during the day.', ['sleep','sleeping','work','schedule','night shift']),
            fact('concern', 'Patient perspective', 'I am worried that I will lose my job if I keep asking for breaks.', ['worries','worried','concerns','concerned','what matters','what concerns']),
            fact('barrier', 'Follow-up barrier', 'I have been putting off appointments because I cannot afford to miss a shift.', ['afford','cost','barrier','appointments','miss a shift','money'], group='Patient context'),
            fact('cbc', 'Synthetic CBC extract', 'Synthetic teaching report: hemoglobin 10.8 g/dL; MCV 74 fL. No other CBC results are supplied in this case.', ['cbc','blood count','lab results','labs','hemoglobin'], group='Investigations', disclosure='record'),
            fact('teaching_note', 'Faculty note', 'Do not infer a final diagnosis from this sparse fictional profile. The task is history elicitation, not treatment.', group='Faculty only', disclosure='faculty_only'),
        ],
        'objectives': [
            objective('history', 'Establish the symptom timeline and functional impact', ['onset','impact'], weight=2),
            objective('medication_safety', 'Elicit medicines and reported allergies', ['medications','allergies'], critical=True, weight=2),
            objective('context', 'Explore sleep, concerns and barriers to follow-up', ['sleep','concern','barrier'], weight=2),
            objective('records', 'Request and review the supplied investigation', ['cbc']),
            objective('empathy', 'Acknowledge the patient’s concern', signal='empathy'),
            objective('opening_skill', 'Open with an invitation to tell the story', signal='open_question'),
        ],
    }
    next(f for f in a['facts'] if f['id']=='barrier')['requires_empathy'] = True
    b = {
        'title': 'An unexpected racing heartbeat', 'setting': 'Clinic interview',
        'description': 'Clarify episodes without accepting leading assumptions or inventing missing results.',
        'author': 'Verity synthetic demo fixture', 'synthetic': True,
        'patient': {'name': 'Maya Ellis', 'age': 34, 'pronouns': 'she/her'},
        'facts': [
            fact('opening', 'Presenting concern', 'My heart has been racing at odd times, and I would like to understand what is happening.', group='Presenting concern', disclosure='initial'),
            fact('onset', 'Episode timeline', 'I first noticed it ten days ago. Each episode lasts about two minutes.', ['when did','how long','started','duration','onset']),
            fact('context', 'Episode context', 'It has happened while I was sitting at my desk, not only when I exercise.', ['exercise','triggers','doing','tell me more','tell me about','rest','desk']),
            fact('associated', 'Associated symptoms', 'I feel shaky during the episodes. I have not fainted.', ['fainted','fainting','other symptoms','associated','shaky']),
            fact('medications', 'Medicines and drinks', 'I use an over-the-counter decongestant and drink two large energy drinks on workdays.', ['medications','medicine','taking','caffeine','energy drinks','supplements']),
            fact('allergies', 'Known allergies', 'I do not know of any medication allergies.', ['allergies','allergic','drug reactions']),
            fact('concern', 'Patient perspective', 'I worry that an episode will happen while I am driving my child.', ['concern','worried','worries','what matters','what concerns']),
            fact('ecg', 'Supplied ECG description', 'Synthetic teaching record: a resting ECG was obtained between episodes. The supplied report states sinus rhythm at 86 beats per minute. No tracing is included.', ['ecg','ekg','electrocardiogram'], group='Investigations', disclosure='record'),
            fact('faculty_note', 'Teaching boundary', 'This fictional case does not establish a cause or a management plan.', group='Faculty only', disclosure='faculty_only'),
        ],
        'objectives': [
            objective('history', 'Clarify timing, context and associated symptoms', ['onset','context','associated'], weight=2),
            objective('exposure', 'Ask about medicines, substances and allergies', ['medications','allergies'], critical=True, weight=2),
            objective('perspective', 'Explore the patient’s own concern', ['concern']),
            objective('records', 'Request the supplied ECG description', ['ecg']),
            objective('permission', 'Ask permission to interview', signal='permission'),
            objective('empathy', 'Acknowledge the patient’s concern', signal='empathy'),
        ],
    }
    c = {
        'title': 'A cough that will not settle', 'setting': 'Primary care interview',
        'description': 'Gather a focused history and separate unavailable evidence from negative findings.',
        'author': 'Verity synthetic demo fixture', 'synthetic': True,
        'patient': {'name': 'Sam Rivera', 'age': 51, 'pronouns': 'he/him'},
        'facts': [
            fact('opening', 'Presenting concern', 'I have a cough that keeps interrupting my conversations.', group='Presenting concern', disclosure='initial'),
            fact('onset', 'Duration', 'It started six weeks ago and has not completely gone away.', ['when did','how long','started','onset']),
            fact('quality', 'Cough description', 'It is usually a dry cough. I notice it more when I lie down.', ['dry','mucus','describe','tell me more','tell me about','lying down']),
            fact('associated', 'Associated symptoms', 'I have not coughed up blood. I sometimes get a sour taste in my mouth.', ['blood','other symptoms','sour taste','anything else']),
            fact('medications', 'Medication history', 'I take lisinopril. I started it about two months ago.', ['medications','medicine','taking','tablets','lisinopril']),
            fact('allergies', 'Reported allergies', 'I get hives after taking sulfonamide antibiotics.', ['allergies','allergic','drug reactions']),
            fact('smoking', 'Exposure history', 'I have never smoked. I work in an office.', ['smoke','smoking','tobacco','work','exposure']),
            fact('concern', 'Patient perspective', 'My father had a long illness, so a symptom that lasts this long worries me.', ['concern','worries','worried','what concerns','what matters']),
            fact('xray', 'Supplied X-ray report', 'Synthetic teaching report: no focal air-space opacity is described. The original image is not included; no additional findings are supplied.', ['x ray','xray','chest film','imaging','radiograph'], group='Investigations', disclosure='record'),
        ],
        'objectives': [
            objective('history', 'Characterize duration, quality and associated symptoms', ['onset','quality','associated'], weight=2),
            objective('medication', 'Clarify medicines and allergies', ['medications','allergies'], critical=True, weight=2),
            objective('context', 'Explore exposure history and patient concerns', ['smoking','concern']),
            objective('records', 'Request the supplied imaging report', ['xray']),
            objective('summary', 'Offer a summary or understanding check', signal='summary'),
        ],
    }
    return copy.deepcopy([a, b, c])
