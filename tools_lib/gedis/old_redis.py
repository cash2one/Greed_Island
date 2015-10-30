# coding: utf-8

import platform
import redis
from redis import ConnectionPool, ConnectionError, BusyLoadingError, AuthenticationError
from tools_lib.host_info import *


REDIS_SERVERS = {
    ONLINE_AL_147_NODE: {
        "host": ONLINE_AL_147_INNER_IP,
        "port": 6379,
        "db": 0,
        "password": "tT6WyYJ5BjkHgNrDblILf18UuieSnsap",
    },
    TEST_DEV_APP: {
        "host": TEST_DEV_APP_IP,
        "port": 6379,
        "db": 0,
        "password": "hSu7aX5KN6ZCqGseM8iR1A9gt3vO0jVE",
    },
}
node = platform.node()
if node in [ONLINE_AL_171_NODE, BL_API_GATEWAY_NODE]:
    node = ONLINE_AL_147_NODE
else:
    node = TEST_DEV_APP
REDIS_CONNECTION_POOL = ConnectionPool(**REDIS_SERVERS.get(node))


class Redis(redis.Redis):
    """
    处理Redis执行命令时可能发生的异常.
    所有view中都应该使用这里的lib.gedis.Redis来替代redis-py的redis.Redis实例化Redis对象
    所有redis命令执行后都应判断返回值，若返回REDIS_CONNECTION_ERROR，则应将写操作retry；
    若返回REDIS_ERROR，则需要从mysql读写数据；
    若返回None则需要根据实际情况判断
    用法：
    from lib.gedis import Redis
    try:
        r = Redis()
        result = r.get('a')
    except:
        ...msql...
    else:
        return result
    """

    def __init__(self, *args, **kwargs):
        kwargs['connection_pool'] = REDIS_CONNECTION_POOL
        redis.Redis.__init__(self, *args, **kwargs)

    def execute_command(self, *args, **kwargs):
        try:
            return redis.Redis.execute_command(self, *args, **kwargs)
        except (ConnectionError, BusyLoadingError, AuthenticationError), ex:
            print 'Redis Error happened when executing command %s %s' % (args, kwargs)
            raise ex
        except Exception, ex:
            print 'Redis Error happened when executing command %s %s: %s' % (args, kwargs, ex)

    def expire_at_today(self, key, hour=0):
        from tools_lib.gtz import TimeZone
        tomorrow = TimeZone.increment_days(TimeZone.local_now())
        self.expireat(key, TimeZone.increment_hours(TimeZone.transfer_datetime_to_beginning(tomorrow), hour))

    def expire_at_this_end_of_month(self, key):
        # 本月月底过期
        from tools_lib.gtz import TimeZone
        local_now = TimeZone.local_now()
        end_of_this_month = TimeZone.utc_to_local(TimeZone.month_range(local_now.year, local_now.month)[1])
        self.expireat(key, end_of_this_month)

    def get_parallel_rank(self, key, member, reverse=True):
        """
        并列排名
        :param key:
        :param member:
        :param reverse: 默认按分数从大到小逆序排序
        :return:
        实现原理
        1> 获取元素的分数
        2> 获取相同分数的第一个元素的排名
        """
        score = self.zscore(key, member)
        if score is None:
            return -1
        try:
            if reverse:
                first_member = self.zrevrangebyscore(name=key, max=score, min=score, start=0, num=1)[0]
                return self.zrevrank(key, first_member) + 1
            else:
                first_member = self.zrangebyscore(name=key, max=score, min=score, start=0, num=1)[0]
                return self.zrank(key, first_member) + 1
        except IndexError:
            return -1
