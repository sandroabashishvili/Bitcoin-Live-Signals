from platform_v2.tools.github_publish_system.sync import prune_removed_news_artifacts
import pytest


def test_scoped_news_deletion_preserves_other_site_content(tmp_path):
    src, dst = tmp_path/'source', tmp_path/'dest'
    (src/'news').mkdir(parents=True)
    (src/'news/index.html').write_text('replacement')
    paths=['news/archive/2026-09-10.html','news/data/news_items_2026-09-10.json','assets/news/old.jpg','news/index.html','spot/dashboard/index.html','assets/logo.jpg']
    for rel in paths:
        p=dst/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('old')
    assert prune_removed_news_artifacts(source=src,dest=dst,dry_run=True)==3
    assert all((dst/rel).exists() for rel in paths)
    assert prune_removed_news_artifacts(source=src,dest=dst)==3
    assert all((dst/rel).exists() for rel in paths[3:])
    (src/'news/index.html').unlink()
    with pytest.raises(ValueError):prune_removed_news_artifacts(source=src,dest=dst)
