beat_schedule = {
    "save-events-every-2s": {
        "task": "app.tasks.save_events_batch",
        "schedule": 2.0,
        "args": (50,),
    }
}
