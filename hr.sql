-- 创建人力资源管理系统用到的数据库和各种表

drop database if exists hr_test;

create database hr_test;

use hr_test;

grant select, insert, update, delete on hr_test.* to 'hr-dba'@'localhost' identified by 'dbdesign';

-- 部门数据，包括部门编号、名称、经理的员工编号、部门最近加入的一个员工的在部门内的编号
create table departments (
    `id` tinyint not null,
    `name` varchar(30) not null,
    `manager_id` char(20),
    `last_num` int not null,
    primary key (`id`)
) engine = innodb default charset=utf8;

-- 级别对应的基本工资
create table level_salary (
    `level` tinyint not null,
    `name` char(20) not null,
    `basic_salary` int not null,
    primary key (`level`)
) engine = innodb default charset=utf8;

-- 员工数据，包括编号、姓名、性别、邮箱、电话、加入日期、级别、部门编号、领导编号
create table employees (
    `id` char(20) not null,
    `name` char(20) not null,
    `sex` bool,
    `email` varchar(50),
    `phone_num` varchar(20),
    `join_date` date not null,
    `leave_date` date,
    `level` tinyint not null,
    `dno` tinyint,
    `leader_id` char(20),
    `password` varchar(50) not null,
    `authority` tinyint not null,
    key `idx_name` (`name`),
    foreign key `fk_dno` (`dno`) 
		    references departments(`id`),
    foreign key `fk_level` (`level`) 
		    references level_salary(`level`),
    primary key (`id`)
) engine = innodb default charset=utf8;

alter table departments add foreign key `fk_mid` (`manager_id`) references employees(`id`);
alter table employees add foreign key `fk_ldr_id` (`leader_id`) references employees(`id`);

-- 技能表，包括编号，技能名称
create table skills (
    `id` smallint not null,
    `name` varchar(100) not null,
    primary key ( `id`)
) engine = innodb default charset=utf8;

-- 员工技能对照表，包括自动增长的主键、员工编号、技能编号
create table emp_skills (
    `id` int not null auto_increment,
    `emp_id` char(20) not null,
    `skill_id` smallint not null,
    `proficiency` tinyint,
    foreign key `fk_emp_id` (`emp_id`) 
		    references employees(`id`),
    foreign key `fk_skill_id` (`skill_id`) 
		    references skills(`id`),
    primary key (`id`)
) engine = innodb default charset=utf8;

-- 员工每月的奖金、罚款数额
create table emp_bonuses_fines (
    `id` int not null auto_increment,
    `emp_id` char(20) not null,
    `month` date not null,
    bonus int,
    fine int,
    foreign key `fk_emp_id` (`emp_id`) 
		    references employees(`id`),
    primary key (`id`)
) engine = innodb default charset=utf8;

-- 员工出勤情况，包括出席信息编号(当天日期+上午/下午+员工编号)、员工编号、签到时间、签离时间、是否请假
create table attendance (
    `id` char(30) not null,
    `emp_id` char(20) not null,
    `in_time` datetime,
    `out_time` datetime,
    `has_vacated` bool not null,
    `vertifier_id` char(20),
    `status` tinyint,
    foreign key `fk_emp_id` (`emp_id`) 
		    references employees(`id`),
    foreign key `fk_vertifier_id` (`vertifier_id`) 
		    references employees(`id`),
    primary key (`id`)
) engine = innodb default charset=utf8;

-- 创建员工月工资视图
create view emp_month_salary as select employees.id,employees.name,month,basic_salary,bonus,fine,(basic_salary+bonus+fine) `sum` from employees,level_salary,emp_bonuses_fines where employees.id = emp_bonuses_fines.emp_id and level_salary.level = employees.level;

-- 在有新员工加入时自动增加部门最新员工编号
create trigger dept_last_num_increase
after insert on employees
for each row
    update departments set last_num = last_num + 1 where id = new.dno;

-- 在有新员工加入时自动计算他的权限级别
create trigger level_to_authority
before insert on employees
for each row
	set new.authority=11-new.level;

-- 在有新员工加入时自动判断是否为部门经理并更新部门的经理编号
delimiter //
create trigger set_dept_manager
after insert on employees
for each row
    begin
        if new.level = 3 then
            update departments set manager_id = new.id where id = new.dno;
        end if;
    end //
delimiter ;
