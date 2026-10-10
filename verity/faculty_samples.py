"""Eight faculty-provided sample profiles from the Challenge 1 CSV.

Answers stay inside that CSV. Teaching instructions stay faculty-only.
No medications, images, or results are added when the source does not supply them.
"""
from .seeds import fact, objective

AUTHOR = 'Faculty-provided sample profile'
NOTE = 'Do not add medications, imaging, or results that this profile does not supply.'


def _note(uuid, summary, extra):
    return fact(
        'faculty_note', 'Faculty note',
        f'Source patient-uuid {uuid}. Summary field: {summary}. {extra} {NOTE}',
        group='Faculty only', disclosure='faculty_only')


def _identity(label):
    return fact(
        'identity', 'Race and ethnicity', f'I am {label}.',
        ['race', 'ethnicity', 'heritage', 'how do you identify', 'background'],
        group='Identity')


def cases():
    vladko = {
        'title': 'Life since the move from Mumbai',
        'setting': 'Outpatient interview',
        'description': 'Ask about life since a recent move, work, diet, tobacco, alcohol, other substance use, and sexual health.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Vladko Bareche', 'age': 31, 'pronouns': 'he/him', 'photo': '/static/patients/vladko-bareche.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'I went to college in India. I work as a TV producer. I moved to Brooklyn from Mumbai eight months ago.', group='Presenting concern', disclosure='initial'),
            fact('living', 'Home and activity', 'I live alone. I walk everywhere, and I play cricket about once a month.', ['live', 'living', 'alone', 'cricket', 'walk', 'exercise', 'activity', 'home']),
            fact('diet', 'Diet', 'I am vegetarian.', ['diet', 'eat', 'food', 'vegetarian', 'meals']),
            fact('smoking', 'Tobacco', 'I smoke one pack of cigarettes a day.', ['smoke', 'smoking', 'cigarettes', 'tobacco', 'pack a day']),
            fact('alcohol', 'Alcohol', 'I drink hard alcohol. On nights when I drink, it is between two and eight drinks, and that happens on two to six nights a week.', ['alcohol', 'drink', 'drinking', 'liquor']),
            fact('cocaine', 'Other substance use', 'I use intranasal cocaine about once or twice a month.', ['cocaine', 'drugs', 'drug use', 'substances', 'other substances']),
            fact('sexual', 'Sexual health', 'I am sexually active primarily with men, and I do not use condoms consistently.', ['sexual', 'sex', 'partners', 'condoms', 'sexually active']),
            fact('support', 'Local support', 'I am managing a demanding creative career, and I have limited local support.', ['support', 'family', 'friends', 'stress', 'career', 'alone here']),
            _identity('Asian Indian'),
            fact('personality', 'How to play this person', 'Faculty direction: quiet, introverted, hard worker. The portrait file is labeled Vadko Bareche; the CSV name is Vladko Bareche.', group='Faculty only', disclosure='faculty_only'),
            _note('5f0f9e8d-b389-4694-8e87-7c78634c7212', 'Vegetarian, smoker, alcohol abuse, and occasional cocaine user.', 'The summary uses the label alcohol abuse; the spoken alcohol fact uses the numeric note instead.'),
        ],
        'objectives': [
            objective('context', 'Ask about home, activity, work stress, and support', ['living', 'support'], weight=2),
            objective('substances', 'Ask about tobacco, alcohol, and other substance use', ['smoking', 'alcohol', 'cocaine'], critical=True, weight=2),
            objective('sexual', 'Ask about sexual health', ['sexual'], weight=2),
            objective('diet', 'Ask about diet', ['diet']),
            objective('identity', 'Ask how he describes his race or ethnicity', ['identity']),
            objective('opening_skill', 'Open with an invitation to tell the story', signal='open_question'),
        ],
    }
    wyatt_bowel = fact('constipation', 'Bowel habit', 'I struggle with constipation, and I avoid talking about it.', ['constipation', 'bowel', 'bowels', 'bathroom', 'stool'])
    wyatt_bowel['requires_empathy'] = True
    wyatt = {
        'title': 'A topic he would rather skip',
        'setting': 'Outpatient interview',
        'description': 'High-school student. Ask about weight, diet, and bowel habits. A cholesterol result is on record. He avoids one of these topics until the conversation acknowledges him.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Wyatt Nelson', 'age': 18, 'pronouns': 'he/him', 'photo': '/static/patients/wyatt-nelson.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'I am a high school student.', group='Presenting concern', disclosure='initial'),
            fact('weight', 'Body weight', 'My BMI is 32.', ['weight', 'bmi', 'how much do you weigh']),
            fact('lipids', 'Supplied cholesterol values', 'Faculty-supplied values: total cholesterol 235, LDL 145. No other cholesterol results are in this profile.', ['cholesterol', 'lipid', 'ldl', 'labs', 'lab results', 'blood test'], group='Investigations', disclosure='record'),
            fact('diet', 'Food pattern', 'I dislike fruits and vegetables.', ['diet', 'eat', 'food', 'fruits', 'vegetables', 'fiber']),
            wyatt_bowel,
            _identity('White American'),
            fact('personality', 'How to play this person', 'Faculty direction: shy, resistant, sensitive.', group='Faculty only', disclosure='faculty_only'),
            _note('4d619156-3250-4212-8399-129f3280fab1', 'Obesity, Dyslipidemia, Constipation.', 'He needs developmentally appropriate counseling around fiber, fat intake, bowel health, and cardiovascular risk. His actual fat intake is not supplied.'),
        ],
        'objectives': [
            objective('weight', 'Ask about weight', ['weight'], weight=2),
            objective('diet', 'Ask about fruits, vegetables, and fiber', ['diet'], weight=2),
            objective('bowel', 'Acknowledge him, then ask about bowel habits', ['constipation'], critical=True, weight=2),
            objective('records', 'Request the supplied cholesterol values', ['lipids']),
            objective('identity', 'Ask how he describes his race or ethnicity', ['identity']),
            objective('empathy', 'Acknowledge a feeling before the avoided topic', signal='empathy'),
        ],
    }
    walter = {
        'title': 'Between hospital stays',
        'setting': 'Hospital interview',
        'description': 'Ask about home life, why he is in the hospital, his diet, and who he likes talking with on the unit.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Walter Greene', 'age': 72, 'pronouns': 'he/him', 'photo': '/static/patients/walter-greene.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'I am a retired janitor, and I live alone.', group='Presenting concern', disclosure='initial'),
            fact('heart', 'Heart failure', 'I have heart failure, and I come back to the hospital often.', ['heart', 'heart failure', 'why are you here', 'hospital', 'admission', 'what brings']),
            fact('diet', 'Diet', 'I do not follow the diet.', ['diet', 'food', 'eat', 'following the diet', 'meal plan']),
            fact('team', 'People he talks with', 'I like talking shop with physical therapy and the nurses.', ['physical therapy', 'pt', 'nurses', 'who do you talk', 'staff']),
            _identity('African-American'),
            fact('personality', 'How to play this person', 'Faculty direction: grumpy but humorous, dislikes students. Summary label: frequent flier.', group='Faculty only', disclosure='faculty_only'),
            _note('3fc37c34-eb88-4b71-9406-3ec6c13dbb9f', 'Heart Failure, frequent flier.', 'No medicines, weights, or ejection fraction are supplied.'),
        ],
        'objectives': [
            objective('illness', 'Ask why he is in the hospital', ['heart'], critical=True, weight=2),
            objective('diet', 'Ask whether he follows his diet', ['diet'], weight=2),
            objective('team', 'Ask who he talks with on the unit', ['team']),
            objective('identity', 'Ask how he describes his race or ethnicity', ['identity']),
            objective('opening_skill', 'Open with an invitation to tell the story', signal='open_question'),
        ],
    }
    marcus = {
        'title': 'Full early, and unsure about food',
        'setting': 'Outpatient interview',
        'description': 'Ask about work, a longer illness, appetite, and whether diet changes his symptoms. A classification and a body measurement are on record.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Marcus Ramirez', 'age': 59, 'pronouns': 'he/him', 'photo': '/static/patients/marcus-ramirez.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'I am a sales associate at Westwood One.', group='Presenting concern', disclosure='initial'),
            fact('heart', 'Heart failure', 'I have been living with heart failure for about a year.', ['heart', 'heart failure', 'illness', 'diagnosis', 'how long']),
            fact('appetite', 'Early satiety', 'I get full early when I eat.', ['appetite', 'eating', 'satiety', 'full', 'meals', 'hungry']),
            fact('diet', 'Diet and symptoms', 'I am uncertain about the role of diet in controlling my symptoms.', ['diet', 'food', 'symptom control', 'what I eat']),
            fact('bmi', 'Supplied BMI', 'Faculty-supplied measurement: BMI 19. No other body measurements are in this profile.', ['bmi', 'weight', 'body measurement'], group='Investigations', disclosure='record'),
            fact('stage', 'Supplied classification', 'Faculty-supplied classification: heart failure, NYHA Stage C. No other staging detail is supplied.', ['nyha', 'stage', 'classification', 'how severe'], group='Investigations', disclosure='record'),
            _identity('Hispanic/Latino'),
            fact('personality', 'How to play this person', 'Faculty direction: cautious, stoic, practical.', group='Faculty only', disclosure='faculty_only'),
            _note('e7471161-b487-4804-b009-1b49681247b6', 'Heart Failure NYHA Stage C.', 'He needs clear explanations of heart-failure pathophysiology and management. Medicines are not supplied.'),
        ],
        'objectives': [
            objective('illness', 'Establish the heart-failure history', ['heart'], critical=True, weight=2),
            objective('eating', 'Ask about appetite and the role of diet', ['appetite', 'diet'], weight=2),
            objective('records', 'Request the supplied BMI and NYHA classification', ['bmi', 'stage']),
            objective('identity', 'Ask how he describes his race or ethnicity', ['identity']),
            objective('opening_skill', 'Open with an invitation to tell the story', signal='open_question'),
        ],
    }
    omar = {
        'title': 'Cholesterol, and a reluctance to take medicine',
        'setting': 'Outpatient interview',
        'description': 'Ask about work and how he feels about taking medicines. Lipid results and body measurements are on record.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Omar Sinclair', 'age': 45, 'pronouns': 'he/him', 'photo': '/static/patients/omar-sinclair.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'I work as a small aircraft mechanic.', group='Presenting concern', disclosure='initial'),
            fact('medicines', 'Medicines', 'I am uncomfortable with taking medications.', ['medication', 'medications', 'medicine', 'statin', 'pills', 'taking']),
            fact('lipids', 'Supplied lipid panel', 'Faculty-supplied lipid panel: total cholesterol 260, LDL 195, HDL 30. No other results are supplied.', ['cholesterol', 'lipid', 'ldl', 'hdl', 'labs', 'lab results'], group='Investigations', disclosure='record'),
            fact('body', 'Supplied body measurements', 'Faculty-supplied measurements: BMI 29 and waist circumference 43 inches.', ['bmi', 'weight', 'waist', 'measurements'], group='Investigations', disclosure='record'),
            _identity('African-American'),
            fact('personality', 'How to play this person', 'Faculty direction: skeptical, independent, practical.', group='Faculty only', disclosure='faculty_only'),
            _note('b5814549-fd2b-42a2-af78-9b681ad6f268', 'Dyslipidemia.', 'He needs support understanding LDL versus HDL, the purpose of statins, and realistic dietary approaches. His current diet is not supplied.'),
        ],
        'objectives': [
            objective('medicines', 'Ask how he feels about taking medications', ['medicines'], critical=True, weight=2),
            objective('records', 'Request the supplied lipid panel and body measurements', ['lipids', 'body'], weight=2),
            objective('identity', 'Ask how he describes his race or ethnicity', ['identity']),
            objective('teach_back', 'Invite him to explain the numbers back', signal='teach_back'),
        ],
    }
    nisha_feeling = fact('coping', 'How she is feeling', 'I am emotionally overwhelmed.', ['overwhelmed', 'anxious', 'coping', 'how are you feeling', 'scared', 'worried'])
    nisha_feeling['requires_empathy'] = True
    nisha = {
        'title': 'A first hospitalization',
        'setting': 'Hospital interview',
        'description': 'This is her first hospitalization. Ask what she was told and how she is coping. She will want the explanation.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Nisha Patel', 'age': 29, 'pronouns': 'she/her', 'photo': '/static/patients/nisha-patel.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'I work in IT. I am married. This is my first hospitalization.', group='Presenting concern', disclosure='initial'),
            fact('diagnosis', 'What she was told', 'I was newly diagnosed with multiple sclerosis. I want to understand every detail.', ['diagnosis', 'multiple sclerosis', 'ms', 'what is wrong', 'what did they tell', 'told you']),
            nisha_feeling,
            _identity('Indian-American'),
            fact('personality', 'How to play this person', 'Faculty direction: intelligent, anxious, wants to understand every detail. She challenges providers with questions.', group='Faculty only', disclosure='faculty_only'),
            _note('e162495c-81de-4cb5-9110-8d69b538dcb2', 'Young adult with newly diagnosed MS.', 'No MRI, medications, or exam findings are supplied.'),
        ],
        'objectives': [
            objective('diagnosis', 'Ask what she was told', ['diagnosis'], critical=True, weight=2),
            objective('coping', 'Acknowledge her, then ask how she is coping', ['coping'], weight=2),
            objective('identity', 'Ask how she describes her race or ethnicity', ['identity']),
            objective('empathy', 'Acknowledge how overwhelming this is', signal='empathy'),
            objective('teach_back', 'Invite her to say what she understands', signal='teach_back'),
        ],
    }
    yvette = {
        'title': 'What the doctor said',
        'setting': 'Outpatient interview',
        'description': 'She did not understand what her doctor said. Ask about work, the condition she was given, and what confuses her. A blood pressure and a BMI are on record.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Yvette Armstrong', 'age': 64, 'pronouns': 'she/her', 'photo': '/static/patients/yvette-armstrong.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'My doctor told me, but I just did not understand what she said.', group='Presenting concern', disclosure='initial'),
            fact('work', 'Work and education', 'I am a full-time state employee. I have an associate\'s degree in political science.', ['work', 'job', 'school', 'education', 'degree', 'what do you do']),
            fact('pressure', 'What confuses her', 'I was recently diagnosed with stage II hypertension. I am confused about sodium and salt.', ['blood pressure', 'hypertension', 'sodium', 'salt', 'diagnosis', 'confused']),
            fact('bp', 'Supplied blood pressure', 'Faculty-supplied blood pressure: 155/110 mmHg. No other vital signs are supplied.', ['reading', 'numbers', '155', 'vital signs', 'blood pressure result'], group='Investigations', disclosure='record'),
            fact('bmi', 'Supplied BMI', 'Faculty-supplied BMI: 34. No other measurements are supplied.', ['bmi', 'weight', 'measurements'], group='Investigations', disclosure='record'),
            _identity('Eastern European American'),
            fact('personality', 'How to play this person', 'Faculty direction: curious, earnest, overwhelmed.', group='Faculty only', disclosure='faculty_only'),
            _note('6ca4cbf9-14ef-427c-b87c-bc9d34ce02b8', 'Hypertension.', 'She needs clear education on what hypertension is, the role of sodium, sodium limits, and the benefits of modest weight loss. Her current diet and medicines are not supplied.'),
        ],
        'objectives': [
            objective('context', 'Ask about work and education', ['work']),
            objective('understanding', 'Ask what she was told and what confuses her', ['pressure'], critical=True, weight=2),
            objective('records', 'Request the supplied blood pressure and BMI', ['bp', 'bmi'], weight=2),
            objective('identity', 'Ask how she describes her race or ethnicity', ['identity']),
            objective('teach_back', 'Invite her to explain it in her own words', signal='teach_back'),
        ],
    }
    dominic = {
        'title': 'Recovering, and not sure whom to trust',
        'setting': 'Hospital interview',
        'description': 'Ask about school, community, what he is recovering from, his family, and how he feels about the hospital.',
        'author': AUTHOR, 'synthetic': True,
        'patient': {'name': 'Dominic Rivera', 'age': 22, 'pronouns': 'he/him', 'photo': '/static/patients/dominic-rivera.jpg'},
        'facts': [
            fact('opening', 'Presenting context', 'I am a college student and a community volunteer.', group='Presenting concern', disclosure='initial'),
            fact('injury', 'Why he is here', 'I am recovering from a gunshot wound on the trauma service.', ['what happened', 'injury', 'gunshot', 'wound', 'trauma', 'why are you here']),
            fact('trust', 'Trust', 'I mistrust authority, and I am skeptical of the healthcare system.', ['trust', 'doctors', 'hospital', 'authority', 'comfortable here']),
            fact('family', 'Younger siblings', 'I am protective of my younger siblings.', ['family', 'siblings', 'brothers', 'sisters', 'home']),
            _identity('Puerto Rican'),
            fact('personality', 'How to play this person', 'Faculty direction: resilient, skeptical of the healthcare system, protective of younger siblings. This profile is marked for cultural-humility scenarios.', group='Faculty only', disclosure='faculty_only'),
            _note('4720727a-f153-465d-9e36-2b41884a1358', 'Recovering from gunshot wound, trauma service.', 'Wound location, surgery, medicines, and imaging are not supplied.'),
        ],
        'objectives': [
            objective('injury', 'Ask what he is recovering from', ['injury'], critical=True, weight=2),
            objective('trust', 'Ask how he feels about the hospital and authority', ['trust'], weight=2),
            objective('family', 'Ask about his family', ['family']),
            objective('identity', 'Ask how he describes his race or ethnicity', ['identity']),
            objective('empathy', 'Acknowledge what this has been like', signal='empathy'),
        ],
    }
    return [vladko, wyatt, walter, marcus, omar, nisha, yvette, dominic]
