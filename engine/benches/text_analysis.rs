use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use ukip_engine::pipelines::text_analysis::{keywords::TfIdfExtractor, tokenizer::tokenize};

fn make_corpus(n_docs: usize, words_per_doc: usize) -> Vec<Vec<String>> {
    let word_pool: Vec<String> = (0..200).map(|i| format!("word{}", i)).collect();
    (0..n_docs)
        .map(|i| {
            (0..words_per_doc)
                .map(|j| word_pool[(i * 7 + j * 13) % word_pool.len()].clone())
                .collect()
        })
        .collect()
}

fn bench_tfidf(c: &mut Criterion) {
    let mut group = c.benchmark_group("text_analysis");

    for n_docs in [10, 100, 1000] {
        let corpus = make_corpus(n_docs, 50);
        let extractor = TfIdfExtractor::new(10, 0.0, 0.95);

        group.bench_with_input(
            BenchmarkId::new("tfidf_extract", n_docs),
            &corpus,
            |b, corpus| {
                b.iter(|| {
                    let _ = extractor.extract(corpus);
                });
            },
        );
    }

    group.finish();
}

fn bench_tokenize(c: &mut Criterion) {
    let text = "The quick brown fox jumps over the lazy dog. \
                Machine learning is transforming the field of natural language processing. \
                Deep neural networks achieve state of the art results on many benchmark tasks.";

    c.bench_function("tokenize_abstract", |b| {
        b.iter(|| tokenize(text));
    });
}

criterion_group!(benches, bench_tfidf, bench_tokenize);
criterion_main!(benches);
