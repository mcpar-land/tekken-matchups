# Tekken Matchup Aggregation

## Pre-Building

Pull all ranked data from wavu. This can take a very long time (a day), but can be stopped and resumed while retaining progress.
```
just scrape  
```

Aggregate data into intermediate formats. This can take a few minutes.
```
just aggregate
```

Start development server.
```
just dev
```

To build without development server:
```
just build
```

The scraping of ranked data takes so long and has such a large storage requirement that executing it via a github action is just not feasible. Looking into a way to host this on pages...
