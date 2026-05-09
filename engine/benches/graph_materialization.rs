use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use ukip_engine::pipelines::graph::nodes::extract_nodes;
use ukip_engine::proto::{Author, Publication};

fn make_publications(n: usize) -> Vec<Publication> {
    (0..n)
        .map(|i| Publication {
            entity_id: i as i64,
            title: format!("Publication {}", i),
            source_title: Some("Nature Reviews".to_string()),
            authors: vec![
                Author {
                    name: format!("Author A{}", i),
                    order: Some(1),
                    ..Default::default()
                },
                Author {
                    name: format!("Author B{}", i),
                    order: Some(2),
                    ..Default::default()
                },
            ],
            concepts: vec!["Machine Learning".to_string(), "AI".to_string()],
            ..Default::default()
        })
        .collect()
}

fn bench_node_extraction(c: &mut Criterion) {
    let mut group = c.benchmark_group("graph_materialization");

    for size in [100, 1000, 2841, 10000] {
        let pubs = make_publications(size);
        group.bench_with_input(
            BenchmarkId::new("extract_nodes", size),
            &pubs,
            |b, pubs| {
                b.iter(|| {
                    for pub_ in pubs {
                        let _ = extract_nodes(pub_, None, 1, "science");
                    }
                });
            },
        );
    }

    group.finish();
}

criterion_group!(benches, bench_node_extraction);
criterion_main!(benches);
