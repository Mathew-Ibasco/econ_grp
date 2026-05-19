from django.db import migrations


QUIZ_QUESTIONS = {
    "rail-transport-basics": [
        {
            "question": "What makes rail useful for dense cities?",
            "option_a": "It can move many passengers in limited space.",
            "option_b": "It only works for private cars.",
            "option_c": "It removes the need for stations.",
            "correct_option": "A",
            "explanation": "Rail is efficient because it can move high passenger volumes through fixed corridors.",
        },
        {
            "question": "Which item best fits rail transport basics?",
            "option_a": "Tracks, trains, stations, and passenger movement.",
            "option_b": "Airline routes only.",
            "option_c": "Individual parking spaces.",
            "correct_option": "A",
            "explanation": "The basics focus on the core rail system and how people or goods move through it.",
        },
        {
            "question": "Why is rail often linked to lower congestion?",
            "option_a": "It shifts many trips away from roads.",
            "option_b": "It increases the number of private vehicles.",
            "option_c": "It blocks all other transport modes.",
            "correct_option": "A",
            "explanation": "When rail is reliable, it can reduce dependence on road travel.",
        },
    ],
    "philippine-rail-systems": [
        {
            "question": "Which systems are part of the Philippine rail context shown on the site?",
            "option_a": "MRT, LRT, PNR, subway, and commuter rail projects.",
            "option_b": "Only international bullet trains.",
            "option_c": "Only airport terminals.",
            "correct_option": "A",
            "explanation": "The topic groups Philippine rail lines and major current rail projects.",
        },
        {
            "question": "What is one goal of major Philippine rail projects?",
            "option_a": "Improve mobility and reduce congestion.",
            "option_b": "Remove public transport options.",
            "option_c": "Make cities less connected.",
            "correct_option": "A",
            "explanation": "Rail projects are presented as tools for connectivity and congestion relief.",
        },
        {
            "question": "Which project is linked to the NSCR materials?",
            "option_a": "North-South Commuter Railway.",
            "option_b": "A shipping-only canal.",
            "option_c": "A private parking project.",
            "correct_option": "A",
            "explanation": "NSCR refers to the North-South Commuter Railway.",
        },
    ],
    "mobility-economy": [
        {
            "question": "How can rail support economic productivity?",
            "option_a": "By improving access to jobs, services, and business districts.",
            "option_b": "By making travel less reliable.",
            "option_c": "By isolating neighborhoods.",
            "correct_option": "A",
            "explanation": "Better access can reduce travel friction and support economic activity.",
        },
        {
            "question": "What does accessibility mean in this topic?",
            "option_a": "The ability to reach opportunities and services.",
            "option_b": "The number of decorative signs at stations.",
            "option_c": "The removal of public spaces.",
            "correct_option": "A",
            "explanation": "Accessibility is about reaching places, services, people, and opportunities.",
        },
        {
            "question": "Which effect is connected to transit-oriented growth?",
            "option_a": "Development near transport hubs.",
            "option_b": "Less connection between land use and transport.",
            "option_c": "No change in mobility patterns.",
            "correct_option": "A",
            "explanation": "Rail can encourage development around stations and corridors.",
        },
    ],
    "rail-gallery": [
        {
            "question": "What is the gallery snapshot meant to collect?",
            "option_a": "Images and videos related to rail systems and mobility.",
            "option_b": "Only unrelated advertisements.",
            "option_c": "Only login records.",
            "correct_option": "A",
            "explanation": "The gallery groups visual examples of rail transport and urban mobility.",
        },
        {
            "question": "Why are maps useful in the gallery?",
            "option_a": "They show routes, corridors, and network connections.",
            "option_b": "They hide the transport network.",
            "option_c": "They replace every written source.",
            "correct_option": "A",
            "explanation": "Maps help users understand spatial relationships in rail systems.",
        },
        {
            "question": "Which media type can appear in the gallery data?",
            "option_a": "Image or video.",
            "option_b": "Password only.",
            "option_c": "Cart contents only.",
            "correct_option": "A",
            "explanation": "The media gallery model supports images and videos.",
        },
    ],
    "rail-history-resource": [
        {
            "question": "Why is rail history useful for this site?",
            "option_a": "It explains how rail became important to cities and regions.",
            "option_b": "It proves rail has no role in development.",
            "option_c": "It only lists unrelated inventions.",
            "correct_option": "A",
            "explanation": "Historical context helps explain rail's role in modern mobility.",
        },
        {
            "question": "Which topic is naturally linked to rail history?",
            "option_a": "Rail Transport Basics.",
            "option_b": "Password validation.",
            "option_c": "User logout buttons.",
            "correct_option": "A",
            "explanation": "History is closely related to understanding basic rail transport concepts.",
        },
        {
            "question": "What does a historical resource add to study?",
            "option_a": "Background context for current transport systems.",
            "option_b": "A way to avoid sources.",
            "option_c": "A replacement for all data.",
            "correct_option": "A",
            "explanation": "It gives background for interpreting today's systems.",
        },
    ],
    "world-bank-mobility-resource": [
        {
            "question": "What does the World Bank mobility resource connect to?",
            "option_a": "Urban mobility, accessibility, and livable cities.",
            "option_b": "Only entertainment videos.",
            "option_c": "Only user registration.",
            "correct_option": "A",
            "explanation": "The resource supports the site's mobility and city-development theme.",
        },
        {
            "question": "Which topic is most closely related to this resource?",
            "option_a": "Accessibility, Mobility & The Economy.",
            "option_b": "Unrelated account settings.",
            "option_c": "Only decorative images.",
            "correct_option": "A",
            "explanation": "The resource links mobility investment with livability and accessibility.",
        },
        {
            "question": "Why would a user save this resource?",
            "option_a": "To revisit evidence about urban mobility investment.",
            "option_b": "To delete all topic links.",
            "option_c": "To replace the whole dashboard.",
            "correct_option": "A",
            "explanation": "It is useful as a supporting source for the economics and mobility discussion.",
        },
    ],
}


def seed_quizzes(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    QuizQuestion = apps.get_model("econ", "QuizQuestion")

    for topic_key, questions in QUIZ_QUESTIONS.items():
        topic = Topic.objects.filter(key=topic_key).first()
        if not topic:
            continue
        for order, question_data in enumerate(questions, start=1):
            QuizQuestion.objects.update_or_create(
                topic=topic,
                question=question_data["question"],
                defaults={
                    "option_a": question_data["option_a"],
                    "option_b": question_data["option_b"],
                    "option_c": question_data["option_c"],
                    "correct_option": question_data["correct_option"],
                    "explanation": question_data["explanation"],
                    "order": order,
                },
            )


def unseed_quizzes(apps, schema_editor):
    QuizQuestion = apps.get_model("econ", "QuizQuestion")
    QuizQuestion.objects.filter(
        question__in=[
            question["question"]
            for questions in QUIZ_QUESTIONS.values()
            for question in questions
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0017_quizattempt_quizquestion_studyitemprogress_topicnote"),
    ]

    operations = [
        migrations.RunPython(seed_quizzes, unseed_quizzes),
    ]
