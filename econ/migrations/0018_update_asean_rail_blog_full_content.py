from django.db import migrations


BLOG_SLUG = "asean-rail-systems-vs-the-philippine-rail-system"

PAGE_1 = (
    "BLOG 4: ASEAN Rail Systems VS the Philippine Rail System Picture: - "
    "https://cache2.travelfish.org/b/assets/2015/gallery/largeR/gallery_planning_largeR__1509364634.jpg "
    "Rail transport has long been a cornerstone of mobility in Southeast Asia. Countries like Thailand, Malaysia, and Singapore have established efficient, modern rail networks that connect urban and rural areas, facilitate trade, and support tourism (Gucilatar, 2017). Meanwhile, the Philippines continues to lag behind, facing systemic infrastructure challenges that limit mobility and economic potential (Daily Guardian, 2025; Francisco, 2025). Across Southeast Asia, rail networks demonstrate variety and efficiency. Thailand features multiple train classifications, from super express to regular services, connecting cities like Bangkok, Chiang Mai, and Nong Khai (Travelfish). The network is not only a transportation system but also a cultural experience, offering scenic journeys that attract travelers. Malaysia and Singapore have high-speed rail and modern commuter systems linking major urban centers, supporting daily commuters and cross-border travel efficiently (Gucilatar, 2017). Indonesia’s Java rail network provides extensive commuter and intercity connections, while other islands are gradually developing or reopening their rail systems, signaling regional commitment to rail-based mobility (Travelfish). Vietnam and Cambodia also support intercity travel, with Vietnam investing in modernizing routes connecting Hanoi, Saigon, and surrounding provinces (Gucilatar, 2017). The key strengths of ASEAN rail systems include high-density networks, modern trains, multiple service classes, and integrated ticketing options. These elements contribute to reliability and positive traveler experiences (Travelfish; Gucilatar, 2017). In contrast, the Philippines ranks last in ASEAN for overall transport infrastructure quality and performance (Daily Guardian, 2025; Francisco, 2025). According to PIDS, the country’s railway system is severely underdeveloped, with a railway density of only 1.52 kilometers per square kilometer and a low infrastructure quality score of 1.9 out of 7. Most operational lines are concentrated in Metro Manila, and intercity rail connections remain sparse (Francisco, 2025). Budget allocations reflect these challenges. Despite prioritization in the Department of Transportation (DOTr) budget, actual capital outlay for rail systems remains minimal, heavily outweighed by road infrastructure investment (Francisco, 2025). Ongoing projects such as the North-South Commuter Railway, Mindanao Railway, and Metro Manila Subway aim to expand capacity, but nationwide coverage is still limited (Francisco, 2025). Operational issues such as aging trains, frequent delays, and inadequate maintenance further hinder service quality. Unlike ASEAN neighbors, the Philippines has yet to develop high-speed intercity rail or integrated commuter networks capable of supporting both urban and regional travel (Daily Guardian, 2025; Francisco, 2025)."
)

PAGE_2 = (
    "ASEAN trains provide multiple service classes, punctual schedules, modern rolling stock, integrated ticketing, and scenic routes, all of which enhance reliability and passenger experience (Travelfish; Gucilatar, 2017). Philippine trains, in contrast, face overcrowding, frequent service disruptions, and aging infrastructure. Even metro lines operate beyond capacity, creating daily commuter challenges (Francisco, 2025). Tourism integration is another differentiator. In Thailand and Vietnam, trains double as tourist attractions, offering scenic journeys (Travelfish). Philippine railway travel remains largely utilitarian and underutilized for tourism, despite government plans to improve inter-island connectivity (Francisco, 2025). The Philippine Development Plans from 2001 to 2028 outline a gradual shift toward rail modernization. Infrastructure expansion projects include the North-South Commuter Railway, Mindanao Railway, and Metro Manila Subway, aimed at extending coverage across major islands (Francisco, 2025). The government also plans to integrate freight and passenger rail with ports and dry cargo terminals to support trade and reduce road congestion (Francisco, 2025). Modernization initiatives include upgrading rolling stock, adopting integrated ticketing, and collaborating with private and multilateral partners to increase efficiency and innovation (Francisco, 2025). A multimodal approach is also emphasized, with investments in buses, ferries, RORO vessels, and airports complementing rail development to improve mobility nationwide (Gucilatar, 2017; Francisco, 2025). Despite ambitious plans, progress is constrained by fragmented budgeting, lack of centralized infrastructure data, and delayed project implementation (Francisco, 2025). Success will require sustained investment, better planning, and coordinated execution across government agencies (Daily Guardian, 2025; Francisco, 2025). ASEAN rail systems illustrate how strategic investment and modern infrastructure can facilitate urbanization, tourism, and trade (Gucilatar, 2017; Travelfish). The Philippines, while acknowledging these benefits and planning aggressively, continues to face significant gaps in coverage, quality, and operational efficiency. Realizing the potential of Philippine rail transport will require not only increased funding but also integrated planning, data-driven decision-making, and effective coordination between agencies (Daily Guardian, 2025; Francisco, 2025). Sources: Francisco, K. A. (2025, January 6). Transport infrastructure in the Philippines: From plans to actual allocation [Discussion paper]. https://doi.org/10.62986/dp2024.51 Gucilatar, T. (2017, April 20). Traveling in ASEAN: Transport systems in Southeast Asia. Rappler. https://www.rappler.com/newsbreak/iq/167393-traveling-asean-transport-systems-southeast-asia PH ranks last in ASEAN transport infrastructure. (2025, March 18). Daily Guardian. https://www.dailyguardian.com.ph/blog/ph-ranks-last-in-asean-transport-infrastructure"
)

PAGE_3 = (
    "Trains in Southeast Asia. (n.d.). Travelfish. https://www.travelfish.org/travel-planning/trains-in-southeast-asia"
)


def update_blog_four(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    BlogPost = apps.get_model("econ", "BlogPost")

    blog, _ = BlogPost.objects.update_or_create(
        slug=BLOG_SLUG,
        defaults={
            "title": "ASEAN Rail Systems vs the Philippine Rail System",
            "excerpt": "Rail transport has long been a cornerstone of mobility in Southeast Asia.",
            "featured_image_filename": "gallery_planning_largeR__1509364634.jpg",
            "featured_image_url": "https://cache2.travelfish.org/b/assets/2015/gallery/largeR/gallery_planning_largeR__1509364634.jpg",
            "raw_text": "\n\n".join([PAGE_1, PAGE_2, PAGE_3]),
            "body_paragraphs": [PAGE_1, PAGE_2, PAGE_3],
            "keywords": [
                "ASEAN rail systems",
                "Philippine rail system",
                "rail modernization",
                "transport infrastructure",
                "mobility",
                "tourism",
            ],
            "highlights": [],
            "gallery": [
                {
                    "src": "https://cache2.travelfish.org/b/assets/2015/gallery/largeR/gallery_planning_largeR__1509364634.jpg",
                    "alt": "ASEAN rail systems comparison",
                    "caption": "Rail transport in Southeast Asia",
                }
            ],
            "sources": [
                {
                    "url": "https://doi.org/10.62986/dp2024.51",
                    "label": "Francisco, K. A. (2025, January 6). Transport infrastructure in the Philippines: From plans to actual allocation [Discussion paper].",
                },
                {
                    "url": "https://www.rappler.com/newsbreak/iq/167393-traveling-asean-transport-systems-southeast-asia",
                    "label": "Gucilatar, T. (2017, April 20). Traveling in ASEAN: Transport systems in Southeast Asia. Rappler.",
                },
                {
                    "url": "https://www.dailyguardian.com.ph/blog/ph-ranks-last-in-asean-transport-infrastructure",
                    "label": "PH ranks last in ASEAN transport infrastructure. (2025, March 18). Daily Guardian.",
                },
                {
                    "url": "https://www.travelfish.org/travel-planning/trains-in-southeast-asia",
                    "label": "Trains in Southeast Asia. (n.d.). Travelfish.",
                },
            ],
            "order": 4,
        },
    )

    blog.topics.set(Topic.objects.filter(key__in=[
        "rail-transport-basics",
        "philippine-rail-systems",
        "mobility-economy",
    ]))


def revert_blog_four(apps, schema_editor):
    BlogPost = apps.get_model("econ", "BlogPost")
    BlogPost.objects.filter(slug=BLOG_SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0017_seed_asean_rail_blog"),
    ]

    operations = [
        migrations.RunPython(update_blog_four, revert_blog_four),
    ]
