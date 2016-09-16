from __future__ import absolute_import
import logging
from datetime import datetime, timedelta
from traceback import format_tb

import sys

from asyncio import iscoroutinefunction

from pytz import utc

from apscheduler.executors.base import BaseExecutor, run_job
from apscheduler.events import (
    JobExecutionEvent, EVENT_JOB_MISSED, EVENT_JOB_ERROR, EVENT_JOB_EXECUTED)

async def run_coroutine_job(job, jobstore_alias, run_times, logger_name):
    """Coroutine version of run_job()."""
    events = []
    logger = logging.getLogger(logger_name)
    for run_time in run_times:
        # See if the job missed its run time window, and handle possible misfires accordingly
        if job.misfire_grace_time is not None:
            difference = datetime.now(utc) - run_time
            grace_time = timedelta(seconds=job.misfire_grace_time)
            if difference > grace_time:
                events.append(JobExecutionEvent(EVENT_JOB_MISSED, job.id, jobstore_alias,
                                                run_time))
                logger.warning('Run time of job "%s" was missed by %s', job, difference)
                continue

        logger.info('Running job "%s" (scheduled at %s)', job, run_time)
        try:
            retval = await job.func(*job.args, **job.kwargs)
        except:
            exc, tb = sys.exc_info()[1:]
            formatted_tb = ''.join(format_tb(tb))
            events.append(JobExecutionEvent(EVENT_JOB_ERROR, job.id, jobstore_alias, run_time,
                                            exception=exc, traceback=formatted_tb))
            logger.exception('Job "%s" raised an exception', job)
        else:
            events.append(JobExecutionEvent(EVENT_JOB_EXECUTED, job.id, jobstore_alias, run_time,
                                            retval=retval))
            logger.info('Job "%s" executed successfully', job)

    return events

class AsyncIOExecutor(BaseExecutor):
    """
    Runs jobs in the default executor of the event loop.

    If the job function is a native coroutine function, it is scheduled to be run directly in the
    event loop as soon as possible. All other functions are run in the event loop's default
    executor which is usually a thread pool.

    Plugin alias: ``asyncio``
    """

    def start(self, scheduler, alias):
        super(AsyncIOExecutor, self).start(scheduler, alias)
        self._eventloop = scheduler._eventloop

    def _do_submit_job(self, job, run_times):
        def callback(f):
            try:
                events = f.result()
            except:
                self._run_job_error(job.id, *sys.exc_info()[1:])
            else:
                self._run_job_success(job.id, events)

        if iscoroutinefunction(job.func):
            coro = run_coroutine_job(job, job._jobstore_alias, run_times, self._logger.name)
            f = self._eventloop.create_task(coro)
        else:
            f = self._eventloop.run_in_executor(None, run_job, job, job._jobstore_alias, run_times,
                                                self._logger.name)

        f.add_done_callback(callback)
