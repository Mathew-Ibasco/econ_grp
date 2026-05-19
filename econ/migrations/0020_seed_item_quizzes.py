from django.db import migrations


BLOG_QUIZZES = {
    "rail-transport-supports-economic-development": [
        {
            "question": "What is one economic benefit of rail transport described in the blog?",
            "option_a": "It can connect people, goods, and businesses more efficiently.",
            "option_b": "It removes the need for all other transport.",
            "option_c": "It only benefits private car owners.",
            "correct_option": "A",
        },
        {
            "question": "Why can rail help sustainable urban growth?",
            "option_a": "It supports reliable mass transport and can reduce car dependence.",
            "option_b": "It increases road congestion.",
            "option_c": "It prevents access to downtown areas.",
            "correct_option": "A",
        },
    ],
    "philippine-railway-system-latest-projects": [
        {
            "question": "Which project is highlighted as a major Philippine rail initiative?",
            "option_a": "Metro Manila Subway.",
            "option_b": "A private-only parking tower.",
            "option_c": "A shipping-only route.",
            "correct_option": "A",
        },
        {
            "question": "What is a likely benefit of Philippine rail projects?",
            "option_a": "Improved connectivity and less congestion over time.",
            "option_b": "Fewer public transport options.",
            "option_c": "Less access between cities.",
            "correct_option": "A",
        },
    ],
}

JOURNAL_QUIZZES = {
    "How railway stations can transform urban mobility and the public realm: The stakeholders’ perspective": [
        {
            "question": "What role do railway stations play in cities?",
            "option_a": "They move people and gather services in the public realm.",
            "option_b": "They only store private vehicles.",
            "option_c": "They remove public interaction.",
            "correct_option": "A",
        }
    ],
    "Enhancing accessibility through rail transit in congested urban areas: A cross-regional analysis": [
        {
            "question": "What does this journal focus on?",
            "option_a": "Accessibility benefits of rail transit in congested areas.",
            "option_b": "Only airline seating.",
            "option_c": "Removing transport data.",
            "correct_option": "A",
        }
    ],
    "The Association between Urban Public Transport Infrastructure and Social Equity and Spatial Accessibility within the Urban Environment: An Investigation of Tramlink in London": [
        {
            "question": "Which concept is central to this journal?",
            "option_a": "Social equity and spatial accessibility.",
            "option_b": "Private parking design only.",
            "option_c": "Unrelated entertainment media.",
            "correct_option": "A",
        }
    ],
    "Governing urban accessibility: moving beyond transport and mobility": [
        {
            "question": "What does urban accessibility support?",
            "option_a": "Access to people, goods, ideas, and services.",
            "option_b": "Isolation from services.",
            "option_c": "Less connection between places.",
            "correct_option": "A",
        }
    ],
    "The role of railway in handling transport services of cities and agglomerations": [
        {
            "question": "What is this journal mainly about?",
            "option_a": "How railway services support urban transport needs.",
            "option_b": "How to avoid public transport.",
            "option_c": "How to remove stations.",
            "correct_option": "A",
        }
    ],
}

VIDEO_QUIZZES = {
    "Railways Reimagined: Reliability, Automation, and Equitable Connectivity": [
        {
            "question": "What idea does this video emphasize?",
            "option_a": "Reliable, automated, and equitable rail connectivity.",
            "option_b": "Removing rail services.",
            "option_c": "Ignoring accessibility.",
            "correct_option": "A",
        }
    ],
    "Driving Inclusivity and Accessibility in Rail Transportation": [
        {
            "question": "What is the main theme of this video?",
            "option_a": "Improving rail accessibility and inclusivity.",
            "option_b": "Making stations harder to use.",
            "option_c": "Avoiding transport planning.",
            "correct_option": "A",
        }
    ],
    "Philippine's Transportation Projects": [
        {
            "question": "What do the projects aim to improve?",
            "option_a": "Mobility, congestion, and economic growth.",
            "option_b": "Only private car storage.",
            "option_c": "Less connection across places.",
            "correct_option": "A",
        }
    ],
    "Railway Bridges over Philippines": [
        {
            "question": "Which investments are mentioned in the video description?",
            "option_a": "MRT-7, NSCR, and Metro Manila Subway.",
            "option_b": "Only ferry terminals.",
            "option_c": "Only private roads.",
            "correct_option": "A",
        }
    ],
    "Social Innovation in Transport and Mobility": [
        {
            "question": "What transport idea is highlighted?",
            "option_a": "Integrated door-to-door mobility using smart systems.",
            "option_b": "No data-sharing in transport.",
            "option_c": "Less commuter access.",
            "correct_option": "A",
        }
    ],
}


def create_question(ItemQuizQuestion, item_type, item_id, order, data):
    ItemQuizQuestion.objects.update_or_create(
        item_type=item_type,
        item_id=item_id,
        question=data["question"],
        defaults={
            "option_a": data["option_a"],
            "option_b": data["option_b"],
            "option_c": data["option_c"],
            "correct_option": data["correct_option"],
            "order": order,
        },
    )


def seed_item_quizzes(apps, schema_editor):
    BlogPost = apps.get_model("econ", "BlogPost")
    JournalEntry = apps.get_model("econ", "JournalEntry")
    Vlog = apps.get_model("econ", "vlog")
    ItemQuizQuestion = apps.get_model("econ", "ItemQuizQuestion")

    for slug, questions in BLOG_QUIZZES.items():
        blog = BlogPost.objects.filter(slug=slug).first()
        if blog:
            for order, data in enumerate(questions, start=1):
                create_question(ItemQuizQuestion, "blog", blog.id, order, data)

    for title, questions in JOURNAL_QUIZZES.items():
        journal = JournalEntry.objects.filter(title=title).first()
        if journal:
            for order, data in enumerate(questions, start=1):
                create_question(ItemQuizQuestion, "journal", journal.id, order, data)

    for title, questions in VIDEO_QUIZZES.items():
        video = Vlog.objects.filter(title=title).first()
        if video:
            for order, data in enumerate(questions, start=1):
                create_question(ItemQuizQuestion, "video", video.vlogID, order, data)


def unseed_item_quizzes(apps, schema_editor):
    ItemQuizQuestion = apps.get_model("econ", "ItemQuizQuestion")
    questions = []
    for group in (BLOG_QUIZZES, JOURNAL_QUIZZES, VIDEO_QUIZZES):
        for entries in group.values():
            questions.extend(entry["question"] for entry in entries)
    ItemQuizQuestion.objects.filter(question__in=questions).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0019_itemquizquestion_itemquizattempt_itemnote"),
    ]

    operations = [
        migrations.RunPython(seed_item_quizzes, unseed_item_quizzes),
    ]
