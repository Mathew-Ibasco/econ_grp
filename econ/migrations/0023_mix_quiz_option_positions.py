from django.db import migrations


TARGET_OPTIONS = ("B", "C", "A")
OPTION_FIELDS = {
    "A": "option_a",
    "B": "option_b",
    "C": "option_c",
}


def mix_question_options(question, seed):
    current_correct = question.correct_option
    correct_text = getattr(question, OPTION_FIELDS[current_correct])
    distractors = [
        getattr(question, OPTION_FIELDS[option])
        for option in ("A", "B", "C")
        if option != current_correct
    ]
    target_correct = TARGET_OPTIONS[seed % len(TARGET_OPTIONS)]
    next_distractor = iter(distractors)

    for option in ("A", "B", "C"):
        value = correct_text if option == target_correct else next(next_distractor)
        setattr(question, OPTION_FIELDS[option], value)

    question.correct_option = target_correct
    question.save(update_fields=["option_a", "option_b", "option_c", "correct_option"])


def mix_options(apps, schema_editor):
    QuizQuestion = apps.get_model("econ", "QuizQuestion")
    ItemQuizQuestion = apps.get_model("econ", "ItemQuizQuestion")

    for index, question in enumerate(QuizQuestion.objects.order_by("topic_id", "order", "id")):
        mix_question_options(question, index)

    for index, question in enumerate(ItemQuizQuestion.objects.order_by("item_type", "item_id", "round_number", "order", "id")):
        mix_question_options(question, index)


def unmix_options(apps, schema_editor):
    QuizQuestion = apps.get_model("econ", "QuizQuestion")
    ItemQuizQuestion = apps.get_model("econ", "ItemQuizQuestion")

    for question in QuizQuestion.objects.all():
        mix_question_options(question, 2)

    for question in ItemQuizQuestion.objects.all():
        mix_question_options(question, 2)


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0022_seed_item_quiz_rounds"),
    ]

    operations = [
        migrations.RunPython(mix_options, unmix_options),
    ]
