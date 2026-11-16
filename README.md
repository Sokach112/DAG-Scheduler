# DAG Scheduler

## Data Flow

```text
   events: List[Event]
        │
        v
   Plan(events, origin)          <- Check the uniqueness of eid, the existence of dependency
        │  plan.index: Dict[str, Event]
        │  plan.origin: datetime.datetime
        v
   CPMScheduler(plan)            <- topo_order (cycle detect), build graph
        │
        v
   scheduler.run()               <- forward_pass + backward_pass
        │  Write back every Event: est/eft/lst/lft/slack
        v
   CPMResult                     <- makespan, critical_path, overdue, events
        │
        v
   analysis.*(plan, result)      <- Read-only
        │  gantt_data / deadline_violations / feasibility_report / render_gantt_text
        v
   List[Dict] / FeasibilityReport / str
```

