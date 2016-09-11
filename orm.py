#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'cx'

import asyncio,logging

import aiomysql

def log(sql,args=()):
    '''日志记录函数'''
    logging.info('SQL: %s , %s' % (sql, str(args)))

async def create_pool(loop,**kw):
    '''创建数据库连接池，默认情况下主机为localhost,端口号为3306,
    字符集为UTF-8，自动提交，最大值为10,最小为1'''
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host','localhost'),
        port = kw.get('port',3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        charset = kw.get('charset','utf8'),
        autocommit = kw.get('autocommit',True),
        maxsize = kw.get('maxsize',10),
        minsize = kw.get('minsize',1),
        loop = loop
    )

async def close_pool():
    '''异步关闭连接池'''
    logging.info('close database connection pool...')
    global __pool
    __pool.close()
    await __pool.wait_closed()

async def select(sql,args,size=None):
    '''执行sql所描述的select语句，args用于取代sql中的占位符，
    size表示要获得的记录条数'''
    log(sql,args)
    global __pool
    #with...as语句表示从连接池中得到1个连接，在语句块结束时会自动close
    with (await __pool) as conn:
        #得到字典型游标
        cur = await conn.cursor(aiomysql.DictCursor)
        #把sql语句的占位符?替换为mysql的占位符%s
        await cur.execute(sql.replace('?','%s'),args or ())
        if size:
            rs = await cur.fetchmany(size) #得到size条记录
        else:
            rs = await cur.fetchall() #得到表中所有记录
        await cur.close()
    logging.info('rows returned: %s' % len(rs))
    #rs是一个字典组成的列表，类似[{'a':1,'b':2},{'a':3,'b':3}]
    return rs

async def execute(sql,args):
    '''执行sql所描述的insert,update,delete语句，args用于取代sql中的占位符'''
    log(sql, args)
    global __pool
    with (await __pool) as conn:
        try:
            cur = await conn.cursor()
            await cur.execute(sql.replace('?','%s'),args)
            affected = cur.rowcount
            await cur.close()
        except BaseException as e: #捕获到任何异常，都直接向外抛出
            raise
    #返回的是执行语句时影响的行数
    return affected

class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name               #属性列的名字，字符串类型
        self.column_type = column_type #属性列的类型，字符串类型
        self.primary_key = primary_key #是否为主键，布尔类型
        self.default = default         #默认值，视属性列类型而定

    def __str__(self): #在作为字符串输出时被用到，会被子类继承
        return '<%s, %s:%s>' % (self.__class__.__name__, self.name,\
                                self.column_type)

class StringField(Field):
    '''字符串类属性列，默认类型为varchar(100)'''

    def __init__(self, name=None, primary_key=False, default=None,\
                 ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class IntegerField(Field):
    '''整数型属性列，类型为int'''

    def __init__(self, name=None, primary_key=False, default=None):
        super().__init__(name, 'int', primary_key, default)

class BooleanField(Field):
    '''布尔型属性列，类型为boolean'''

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class DatetimeField(Field):
    '''日期属性列，类型为datetime'''

    def __init__(self, name=None, default=None):
        super().__init__(name, 'datetime', False, default)

class ModelMetaClass(type):

    def __new__(cls,name,bases,attrs):
        #排除Model类本身
        if name == 'Model':
            return type.__new__(cls,name,bases,attrs)
        #获取表名:在表名不存在时可以用类名代替
        tableName = attrs.get('__table__',None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        #获取所有的field和主键名
        mappings = dict()
        fields = []
        primaryKey = None
        for k,v in attrs.items():
            #添加类属性里所有Field类的对象到mappings中
            if isinstance(v,Field):
                logging.info('  found mapping: %s ==> %s' % (k,v))
                mappings[k] = v
                if v.primary_key:
                    #找到主键
                    if primaryKey is not None:
                        raise RuntimeError('Duplicate primary key for field:\
                                                                       %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        #从类属性中删除Field属性，避免冲突
        for k in mappings:
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields)) #属性列转义
        attrs['__mappings__'] = mappings         #保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey    #主键属性名
        attrs['__fields__'] = fields             #除主键外的属性名
        #构造默认的SELECT、INSERT、UPDATE、DELETE语句
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey,\
                                         ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % \
                        (tableName, ', '.join(escaped_fields), primaryKey, \
                                                        '?, '*len(fields)+'?')
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName,\
                       ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name\
                                                    or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, \
                                                                    primaryKey)
        return type.__new__(cls, name, bases, attrs)

class Model(dict,metaclass=ModelMetaClass):

    def __init__(self,**kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        '''得到key属性对应的值，不存在则返回None，不抛出异常'''
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        '''得到key属性对应的值，不存在就查找默认值，找不到返回None，不抛出异常'''
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else \
                                                                field.default
                logging.debug('using default value for %s: %s' % (key, \
                                                                  str(value)))
                setattr(self,key,value)
        return value

    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        '''查找表中符合where条件的所有数据'''
        sql = [cls.__select__] #得到标准select语句
        if where:              #sql上添加where部分
            sql.append('where')
            sql.append(where)
        if args is None:       #防止传入为None的args
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:            #sql上添加order by部分
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit:              #sql上添加limit部分，可能有1个或2个参数
            sql.append('limit')
            if isinstance(limit,int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit,tuple):
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args) #join列表sql产生完整的select语句
        #cls(**r)表示通过类名利用字典r创建对象
        #类似kw = {'id':1,'name':'Mark'};User(**kw)
        return [cls(**r) for r in rs] #返回cls类的对象列表

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        '''根据where条件查找，selectField是聚集函数，例如count(*)'''
        #_num_是对查询结果的更名
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1) #只查询一条记录
        if len(rs) == 0: #如果结果集不存在，返回None
            return None
        return rs[0]['_num_'] #返回第一条记录中_num_列的内容

    @classmethod
    async def find(cls, pk):
        '''通过主码对表进行查找'''
        rs = await select('%s where `%s`=?' % (cls.__select__,\
                                               cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0]) #将查找到的记录转化为对象并返回

    async def save(self):
        '''将当前对象中的数据插入到数据库中'''
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)

    async def update(self):
        '''更新数据库中对应当前对象的记录'''
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' \
                                                                         % rows)

    async def remove(self):
        '''将数据库中对应当前对象的记录删除'''
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' \
                                                                         % rows)
