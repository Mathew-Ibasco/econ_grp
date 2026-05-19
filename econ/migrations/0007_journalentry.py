from django.db import migrations, models


JOURNAL_ENTRIES = [
    {
        "title": "How railway stations can transform urban mobility and the public realm: The stakeholders’ perspective",
        "journal_url": "https://www.sciencedirect.com/science/article/pii/S2667091723000031",
        "snippet": "Railway stations are massive infrastructures through which people, products, materials, and energy flow every day. They usually gather a multitude of functions and provide a wide range of services to users based on their respective specific features.",
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
        "snippet": "The efficacy of urban rail transit in reducing the impact of road congestion is the subject of debate in policy and academic communities. Despite huge challenges arising from multifaceted factors such as data limitation, the recently released annual average congestion data enables us to empirically analyze the effect of urban rail transits in terms of their contribution to the average accessibility under road congestion.",
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
        "snippet": "The pursuit of sustainability has been at the forefront of contemporary planning initiatives. However, most recent research has focused on the environmental and economic aspects of developing sustainable urban environment, whilst largely neglecting the social aspects.",
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
        "snippet": "Access to people, goods, ideas and services is the basis of economic development in cities. The better this access, the greater the economic benefits through economies of scale, agglomeration effects and networking advantages.",
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
        "snippet": "The article discusses the changes in handling transport services of cities and agglomerations and the importance of railway in this aspect. Considerations on the transformation of the transport market, being the effect of changes on the market of goods and services and economic growth, the reasons for using railway transport in servicing urban and agglomeration traffic were identified.",
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
        ('econ', '0006_seed_legacy_gallery_entries'),
    ]

    operations = [
        migrations.CreateModel(
            name='JournalEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=350)),
                ('journal_url', models.URLField(max_length=500)),
                ('snippet', models.TextField()),
                ('keywords', models.JSONField(blank=True, default=list)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'journal_entry',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.RunPython(seed_journal_entries, unseed_journal_entries),
    ]
