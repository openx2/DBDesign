#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'cx'

import asyncio, datetime, logging

import pymysql
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from models import Attendance, Employee, EmpBonusFine
from NewAsyncIOExecutor import AsyncIOExecutor

#每次早退罚款20,迟到罚款20,缺勤罚款50
NORMAL            = 0
LEAVE_EARLY       = 1
OVERDUE           = 2
ABSENCE_FROM_DUTY = 4
HAS_VACATED       = 8

def get_part_of_id(dt):
    date = datetime.datetime.strftime(dt,'%Y%m%d')
    time_period = 'pm' if dt.hour>=12 else 'am'
    return date+time_period

def is_absent(attendance):
    time_period = attendance.id[8:]
    if time_period == 'am':
        return attendance.in_time.hour > 9
    else:
        return attendance.in_time.hour > 15

def be_late(attendance):
    time_period = attendance.id[8:]
    if time_period == 'am':
        return attendance.in_time.hour > 7
    else:
        return attendance.in_time.hour > 13

def leave_early(attendance):
    if not attendance.out_time:
        return True
    time_period = attendance.id[8:]
    if time_period == 'am':
        return attendance.out_time.hour < 12
    else:
        return attendance.out_time.hour < 17

def get_employee_fine(attendances):
    if not attendances:
        return 0
    fine = 0
    for atd in attendances:
        if atd.status == NORMAL or atd.status & HAS_VACATED != 0:
            continue
        if atd.status & LEAVE_EARLY != 0:
            fine -= 20
        if atd.status & OVERDUE != 0:
            fine -= 20
        if atd.status & ABSENCE_FROM_DUTY != 0:
            fine -= 50
    return fine

def attendance_manage(loop):
    scheduler = AsyncIOScheduler(executors={'default': AsyncIOExecutor()})
    scheduler.add_job(check_attendance, 'cron', day_of_week='mon-fri',
                                                              hour='13,18')
    scheduler.add_job(insert_records, 'cron', day_of_week='mon-fri',
                                                              hour='13,18')
    scheduler.add_job(determine_fine, 'cron', month='*', day='1', hour='0')
    scheduler.add_job(determine_bonus, 'cron', month='*', day='8', hour='0')
    scheduler.start()

async def check_attendance():
    attendances = await Attendance.findAll('`id` like ?',
                                 get_part_of_id(datetime.datetime.now())+'%')
    if attendances:
        for a in attendances:
            if a.has_vacated:
                a.status = HAS_VACATED
            elif not a.in_time:
                a.status = ABSENCE_FROM_DUTY+LEAVE_EARLY
            elif is_absent(a):
                a.status = ABSENCE_FROM_DUTY if not leave_early(a) else ABSENCE_FROM_DUTY+LEAVE_EARLY
            elif be_late(a):
                a.status = OVERDUE if not leave_early(a) else OVERDUE+LEAVE_EARLY
            elif leave_early(a):
                a.status = LEAVE_EARLY
            else:
                a.status = NORMAL
            await a.update()

async def insert_records():
    #剔除sex为null的管理员和leave_date不为null的离职员工
    employees = await Employee.findAll('`sex` is not null and `leave_date` is\
                                                                       null')
    if employees:
        now = datetime.datetime.now()
        if now.hour>=12:
            next_period = datetime.datetime(now.year, now.month, now.day, 13)
        else:
            next_period = datetime.datetime(now.year, now.month, now.day, 7)
            next_period += datetime.timedelta(days=1)
        for e in employees:
            attendance = Attendance(id=(get_part_of_id(next_period)+e.id),
                           emp_id = e.id, in_time=None, out_time=None,
                           has_vacated=False, vertifier_id=None, status=None)
            try:
                await attendance.save()
            except pymysql.err.IntegrityError as e:
                #如果出现错误1062，则应该是领导帮忙请假时插入了数据，所以不保存
                if e.args[0] == 1062:
                    logging.info('The employee had vacated.')
                else:
                    raise e

async def determine_fine():
    employees = await Employee.findAll('`sex` is not null and `leave_date` is\
                                                                       null')
    if employees:
        last_month = datetime.date.today() - datetime.timedelta(days=1)
        for e in employees:
            #本月该职员的所有出勤记录
            atds = await Attendance.findAll('`emp_id`=? and `id` like ?', [e.id,
                                            last_month.strftime('%Y%m')+'%'])
            ebf = EmpBonusFine(emp_id=e.id, month=last_month, bonus=None,
                                                    fine=getEmployeeFine(atds))
            await ebf.save()

async def determine_bonus():
    last_month = datetime.date.today() - datetime.timedelta(days=8)
    ebfs = await EmpBonusFine.findAll('`month`=? and `bonus` is null',
                            [datetime.datetime.strftime(last_month, '%Y%m%d')])
    for ebf in ebfs:
        ebf.bonus = 0
        await ebf.update()
