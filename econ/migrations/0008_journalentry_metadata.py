from django.db import migrations, models


JOURNAL_ENTRIES = [
    {
        "title": "How railway stations can transform urban mobility and the public realm: The stakeholders’ perspective",
        "journal_url": "https://www.sciencedirect.com/science/article/pii/S2667091723000031",
        "authors": "Lunardon, A., Vladimirova, D., Boucsein, B.",
        "publication_year": 2023,
        "journal_name": "Journal of Urban Mobility",
        "snippet": "Railway stations are massive infrastructures that move people, products, materials, and energy every day. They also gather multiple functions and services for users.",
        "keywords": [
            "railway stations",
            "urban mobility",
            "public realm",
            "stakeholders",
            "sustainable development",
        ],
        "order": 1,
    },
    {
        "title": "Enhancing accessibility through rail transit in congested urban areas: A cross-regional analysis",
        "journal_url": "https://www.sciencedirect.com/science/article/abs/pii/S0966692323002636",
        "authors": "Zhang, H., Zhan, B., Ouyang, M.",
        "publication_year": 2024,
        "journal_name": "Journal of Transport Geography",
        "snippet": "The efficacy of urban rail transit in reducing road congestion remains debated, but congestion data can measure its accessibility benefits.",
        "keywords": [
            "accessibility",
            "rail transit",
            "road congestion",
            "urban planning",
            "Chinese cities",
        ],
        "order": 2,
    },
    {
        "title": "The Association between Urban Public Transport Infrastructure and Social Equity and Spatial Accessibility within the Urban Environment: An Investigation of Tramlink in London",
        "journal_url": "https://www.mdpi.com/2071-1050/11/5/1229",
        "authors": "Cuthill, N., Cao, M., Liu, Y., Gao, X., Zhang, Y.",
        "publication_year": 2019,
        "journal_name": "Sustainability",
        "snippet": "The study notes that sustainability planning has focused on environmental and economic aspects, while social aspects remain underexamined.",
        "keywords": [
            "social equity",
            "spatial accessibility",
            "public transport",
            "light rail",
            "London",
        ],
        "order": 3,
    },
    {
        "title": "Governing urban accessibility: moving beyond transport and mobility",
        "journal_url": "https://www.tandfonline.com/doi/abs/10.1080/23800127.2018.1438149",
        "authors": "Rode, P., da Cruz, N.F.",
        "publication_year": 2018,
        "journal_name": "Applied Mobilities",
        "snippet": "Access to people, goods, ideas, and services underpins economic development in cities and delivers economies of scale, agglomeration effects, and networking advantages.",
        "keywords": [
            "urban accessibility",
            "economic development",
            "mobility",
            "land use",
            "governance",
        ],
        "order": 4,
    },
    {
        "title": "The role of railway in handling transport services of cities and agglomerations",
        "journal_url": "https://www.sciencedirect.com/science/article/pii/S2352146519301310",
        "authors": "Pietrzak, O., Pietrzak, K.",
        "publication_year": 2019,
        "journal_name": "Transportation Research Procedia",
        "snippet": "The article examines how railway services in cities and agglomerations support sustainable development, economic growth, and urban transport demand.",
        "keywords": [
            "railway transport",
            "urban services",
            "agglomerations",
            "sustainable development",
            "economic growth",
        ],
        "order": 5,
    },
]


def seed_journal_entries(apps, schema_editor):
    JournalEntry = apps.get_model("econ", "JournalEntry")

    for entry in JOURNAL_ENTRIES:
        JournalEntry.objects.update_or_create(
            title=entry["title"],
            journal_url=entry["journal_url"],
            defaults={
                "authors": entry["authors"],
                "publication_year": entry["publication_year"],
                "journal_name": entry["journal_name"],
                "snippet": entry["snippet"],
                "keywords": entry["keywords"],
                "order": entry["order"],
            },
        )


def unseed_journal_entries(apps, schema_editor):
    JournalEntry = apps.get_model("econ", "JournalEntry")
    JournalEntry.objects.filter(title__in=[entry["title"] for entry in JOURNAL_ENTRIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0007_journalentry"),
    ]

    operations = [
        migrations.AddField(
            model_name="journalentry",
            name="authors",
            field=models.CharField(default="", max_length=500),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="journalentry",
            name="publication_year",
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="journalentry",
            name="journal_name",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(seed_journal_entries, unseed_journal_entries),
    ]
