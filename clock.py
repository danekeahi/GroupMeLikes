from apscheduler.schedulers.blocking import BlockingScheduler
import main
sched = BlockingScheduler()

@sched.scheduled_job('interval', minutes=45)
def timed_job():
    main.main()


sched.start()