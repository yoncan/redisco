import time
from threading import Thread
import base64
import redis
import unittest
from datetime import date
from redisco import models
from redisco.connection import _get_client
from redisco.models.base import Mutex

class Person(models.Model):
    first_name = models.Attribute()
    last_name = models.Attribute()

    def full_name(self):
        return "%s %s" % (self.first_name, self.last_name,)

    class Meta:
        indices = ['full_name']


class RediscoTestCase(unittest.TestCase):
    def setUp(self):
        self.client = _get_client()
        self.client.flushdb()

    def tearDown(self):
        self.client.flushdb()


class ModelTestCase(RediscoTestCase):

    def test_key(self):
        self.assertEqual('Person', Person._key)

    def test_is_new(self):
        p = Person(first_name="Darken", last_name="Rahl")
        self.assertTrue(p.is_new())

    def test_attributes(self):
        person = Person(first_name="Granny", last_name="Goose")
        self.assertEqual("Granny", person.first_name)
        self.assertEqual("Goose", person.last_name)

    def test_save(self):
        person1 = Person(first_name="Granny", last_name="Goose")
        person1.save()
        person2 = Person(first_name="Jejomar")
        person2.save()

        self.assertEqual('1', person1.id)
        self.assertEqual('2', person2.id)

        jejomar = Person.objects.get_by_id('2')
        self.assertEqual(None, jejomar.last_name)

    def test_update(self):
        person1 = Person(first_name="Granny", last_name="Goose")
        person1.save()

        p = Person.objects.get_by_id('1')
        p.first_name = "Morgan"
        p.last_name = None
        assert p.save()

        p = Person.objects.get_by_id(p.id)
        self.assertEqual("Morgan", p.first_name)
        self.assertEqual(None, p.last_name)

    def test_default_attribute_val(self):
        class User(models.Model):
            views = models.IntegerField(default=199)
            liked = models.BooleanField(default=True)
            disliked = models.BooleanField(default=False)

        u = User()
        self.assertEqual(True, u.liked)
        self.assertEqual(False, u.disliked)
        self.assertEqual(199, u.views)
        assert u.save()

        u = User.objects.all()[0]
        self.assertEqual(True, u.liked)
        self.assertEqual(False, u.disliked)
        self.assertEqual(199, u.views)


    def test_getitem(self):
        person1 = Person(first_name="Granny", last_name="Goose")
        person1.save()
        person2 = Person(first_name="Jejomar", last_name="Binay")
        person2.save()

        p1 = Person.objects.get_by_id(1)
        p2 = Person.objects.get_by_id(2)

        self.assertEqual('Jejomar', p2.first_name)
        self.assertEqual('Binay', p2.last_name)

        self.assertEqual('Granny', p1.first_name)
        self.assertEqual('Goose', p1.last_name)

    def test_manager_create(self):
        person = Person.objects.create(first_name="Granny", last_name="Goose")

        p1 = Person.objects.get_by_id(1)
        self.assertEqual('Granny', p1.first_name)
        self.assertEqual('Goose', p1.last_name)

    def test_indices(self):
        person = Person.objects.create(first_name="Granny", last_name="Goose")
        db = person.db
        key = person.key()
        ckey = Person._key

        index = 'Person:first_name:%s' % base64.b64encode("Granny").replace("\n", "")
        self.assertTrue(index in db.smembers(key['_indices']))
        self.assertTrue("1" in db.smembers(index))

    def test_find(self):
        Person.objects.create(first_name="Granny", last_name="Goose")
        Person.objects.create(first_name="Clark", last_name="Kent")
        Person.objects.create(first_name="Granny", last_name="Mommy")
        Person.objects.create(first_name="Granny", last_name="Kent")
        persons = Person.objects.filter(first_name="Granny")

        self.assertEqual('1', persons[0].id)
        self.assertEqual(3, len(persons))

        persons = Person.objects.filter(first_name="Clark")
        self.assertEqual(1, len(persons))

        # by index
        persons = Person.objects.filter(full_name="Granny Mommy")
        self.assertEqual(1, len(persons))
        self.assertEqual("Granny Mommy", persons[0].full_name())

    
    def test_first(self):
        Person.objects.create(first_name="Granny", last_name="Goose")
        Person.objects.create(first_name="Clark", last_name="Kent")
        Person.objects.create(first_name="Granny", last_name="Mommy")
        Person.objects.create(first_name="Granny", last_name="Kent")
        granny = Person.objects.filter(first_name="Granny").first()
        self.assertEqual('1', granny.id)
        lana = Person.objects.filter(first_name="Lana").first()
        self.assertFalse(lana)


    def test_iter(self):
        Person.objects.create(first_name="Granny", last_name="Goose")
        Person.objects.create(first_name="Clark", last_name="Kent")
        Person.objects.create(first_name="Granny", last_name="Mommy")
        Person.objects.create(first_name="Granny", last_name="Kent")

        for person in Person.objects.all():
            self.assertTrue(person.full_name() in ("Granny Goose",
                "Clark Kent", "Granny Mommy", "Granny Kent",))

    def test_sort(self):
        Person.objects.create(first_name="Zeddicus", last_name="Zorander")
        Person.objects.create(first_name="Richard", last_name="Cypher")
        Person.objects.create(first_name="Richard", last_name="Rahl")
        Person.objects.create(first_name="Kahlan", last_name="Amnell")

        res = Person.objects.order('first_name').all()
        self.assertEqual("Kahlan", res[0].first_name)
        self.assertEqual("Richard", res[1].first_name)
        self.assertEqual("Richard", res[2].first_name)
        self.assertEqual("Zeddicus Zorander", res[3].full_name())

        res = Person.objects.order('-full_name').all()
        self.assertEqual("Zeddicus Zorander", res[0].full_name())
        self.assertEqual("Richard Rahl", res[1].full_name())
        self.assertEqual("Richard Cypher", res[2].full_name())
        self.assertEqual("Kahlan Amnell", res[3].full_name())

    def test_all(self):
        person1 = Person(first_name="Granny", last_name="Goose")
        person1.save()
        person2 = Person(first_name="Jejomar", last_name="Binay")
        person2.save()

        all = Person.objects.all()
        self.assertEqual(list([person1, person2]), list(all))

    def test_limit(self):
        Person.objects.create(first_name="Zeddicus", last_name="Zorander")
        Person.objects.create(first_name="Richard", last_name="Cypher")
        Person.objects.create(first_name="Richard", last_name="Rahl")
        Person.objects.create(first_name="Kahlan", last_name="Amnell")

        res = Person.objects.order('first_name').all().limit(3)
        self.assertEqual(3, len(res))
        self.assertEqual("Kahlan", res[0].first_name)
        self.assertEqual("Richard", res[1].first_name)
        self.assertEqual("Richard", res[2].first_name)

        res = Person.objects.order('first_name').limit(3, offset=1)
        self.assertEqual(3, len(res))
        self.assertEqual("Richard", res[0].first_name)
        self.assertEqual("Richard", res[1].first_name)
        self.assertEqual("Zeddicus", res[2].first_name)


    def test_integer_field(self):
        class Character(models.Model):
            n = models.IntegerField()
            m = models.Attribute()

        Character.objects.create(n=1998, m="A")
        Character.objects.create(n=3100, m="b")
        Character.objects.create(n=1, m="C")

        chars = Character.objects.all()
        self.assertEqual(3, len(chars))
        self.assertEqual(1998, chars[0].n)
        self.assertEqual("A", chars[0].m)

    def test_sort_by_int(self):
        class Exam(models.Model):
            score = models.IntegerField()
            total_score = models.IntegerField()

            def percent(self):
                return int((float(self.score) / self.total_score) * 100)

            class Meta:
                indices = ('percent',)

        Exam.objects.create(score=9, total_score=100)
        Exam.objects.create(score=99, total_score=100)
        Exam.objects.create(score=75, total_score=100)
        Exam.objects.create(score=33, total_score=100)
        Exam.objects.create(score=95, total_score=100)

        exams = Exam.objects.order('score')
        self.assertEqual([9, 33, 75, 95, 99,], [exam.score for exam in exams])
        filtered = Exam.objects.zfilter(score__in=(10, 96))
        self.assertEqual(3, len(filtered))


    def test_filter_date(self):
        from datetime import datetime

        class Post(models.Model):
            name = models.Attribute()
            date = models.DateTimeField()

        dates = (
            datetime(2010, 1, 20, 1, 40, 0),
            datetime(2010, 2, 20, 1, 40, 0),
            datetime(2010, 1, 26, 1, 40, 0),
            datetime(2009, 12, 21, 1, 40, 0),
            datetime(2010, 1, 10, 1, 40, 0),
            datetime(2010, 5, 20, 1, 40, 0),
        )

        i = 0
        for date in dates:
            Post.objects.create(name="Post#%d" % i, date=date)
            i += 1

        self.assertEqual([Post.objects.get_by_id(4)],
                list(Post.objects.filter(date=
                    datetime(2009, 12, 21, 1, 40, 0))))

        lt = (0, 2, 3, 4)
        res = [Post.objects.get_by_id(l + 1) for l in lt]
        self.assertEqual(set(res),
                set(Post.objects.zfilter(
                    date__lt=datetime(2010, 1, 30))))

    def test_validation(self):
        class Person(models.Model):
            name = models.Attribute(required=True)
        p = Person(name="Kokoy")
        self.assertTrue(p.is_valid())

        p = Person()
        self.assertFalse(p.is_valid())
        self.assertTrue(('name', 'required') in p.errors)

    def test_custom_validation(self):
        class Ninja(models.Model):
            def validator(field_name, age):
                if not age or age >= 10:
                    return ((field_name, 'must be below 10'),)
            age = models.IntegerField(required=True, validator=validator)

        nin1 = Ninja(age=9)
        self.assertTrue(nin1.is_valid())

        nin2 = Ninja(age=10)
        self.assertFalse(nin2.is_valid())
        self.assertTrue(('age', 'must be below 10') in nin2.errors)

    def test_overriden_validation(self):
        class Ninja(models.Model):
            age = models.IntegerField(required=True)

            def validate(self):
                if self.age >= 10:
                    self._errors.append(('age', 'must be below 10'))


        nin1 = Ninja(age=9)
        self.assertTrue(nin1.is_valid())

        nin2 = Ninja(age=10)
        self.assertFalse(nin2.is_valid())
        self.assertTrue(('age', 'must be below 10') in nin2.errors)

    def test_load_object_from_key(self):
        class Schedule(models.Model):
            att = models.Attribute()

        class PaperType(models.Model):
            att = models.Attribute()

        assert Schedule.objects.create(att="dinuguan")
        assert Schedule.objects.create(att="chicharon")
        assert Schedule.objects.create(att="Pizza")
        assert Schedule.objects.create(att="Pasta")
        assert Schedule.objects.create(att="Veggies")

        assert PaperType.objects.create(att="glossy")
        assert PaperType.objects.create(att="large")
        assert PaperType.objects.create(att="huge")
        assert PaperType.objects.create(att="A6")
        assert PaperType.objects.create(att="A9")

        o = models.from_key("Schedule:1")
        assert o
        self.assertEqual('1', o.id)
        self.assertEqual(Schedule, type(o))
        o = models.from_key("PaperType:1")
        self.assertEqual('1', o.id)
        self.assertEqual(PaperType, type(o))
        o = models.from_key("Schedule:4")
        self.assertEqual('4', o.id)
        self.assertEqual(Schedule, type(o))
        o = models.from_key("PaperType:5")
        self.assertEqual('5', o.id)
        self.assertEqual(PaperType, type(o))
        o = models.from_key("PaperType:6")
        self.assertTrue(o is None)

        def boom():
            models.from_key("some arbitrary key")
        from redisco.models.exceptions import BadKeyError
        self.assertRaises(BadKeyError, boom)

    def test_uniqueness_validation(self):
        class Student(models.Model):
            student_id = models.Attribute(unique=True)

        student = Student.objects.create(student_id="042231")
        self.assert_(student)

        student = Student(student_id="042231")
        self.assertFalse(student.is_valid())
        self.assert_(('student_id', 'not unique') in student.errors)

        student = Student()
        self.assertTrue(student.is_valid())

    def test_long_integers(self):
        class Tweet(models.Model):
            status_id = models.IntegerField()

        t = Tweet(status_id=int(u'14782201061'))
        self.assertTrue(t.is_valid())
        t.save()

        t = Tweet.objects.get_by_id(t.id)
        self.assertEqual(14782201061, t.status_id)


class Event(models.Model):
    name = models.Attribute(required=True)
    date = models.DateField(required=True)

class DateFieldTestCase(RediscoTestCase):

    def test_attribute(self):
        event = Event(name="Legend of the Seeker Premiere",
                      date=date(2008, 11, 12))
        self.assertEqual(date(2008, 11, 12), event.date)

    def test_saved_attribute(self):
        instance = Event.objects.create(name="Legend of the Seeker Premiere",
                      date=date(2008, 11, 12))
        assert instance
        event = Event.objects.get_by_id(instance.id)
        assert event
        self.assertEqual(date(2008, 11, 12), event.date)

    def test_invalid_date(self):
        event = Event(name="Event #1")
        event.date = 1
        self.assertFalse(event.is_valid())
        self.assertTrue(('date', 'bad type') in event.errors)

    def test_indexes(self):
        d = date.today()
        Event.objects.create(name="Event #1", date=d)
        self.assertTrue('1' in Event._db.smembers(Event._key['all']))
        # zfilter index
        self.assertTrue(Event._db.exists("Event:date"))
        # other field indices
        self.assertEqual(2, Event._db.scard("Event:1:_indices"))
        for index in Event._db.smembers("Event:1:_indices"):
            self.assertTrue(index.startswith("Event:date") or
                    index.startswith("Event:name"))

    def test_auto_now(self):
        class Report(models.Model):
            title = models.Attribute()
            created_on = models.DateField(auto_now_add=True)
            updated_on = models.DateField(auto_now=True)

        r = Report(title="My Report")
        assert r.save()
        r = Report.objects.filter(title="My Report")[0]
        self.assertTrue(isinstance(r.created_on, date))
        self.assertTrue(isinstance(r.updated_on, date))
        self.assertEqual(date.today(), r.created_on)


class Student(models.Model):
    name = models.Attribute(required=True)
    average = models.FloatField(required=True)

class FloatFieldTestCase(RediscoTestCase):
    def test_attribute(self):
        s = Student(name="Richard Cypher", average=86.4)
        self.assertEqual(86.4, s.average)

    def test_saved_attribute(self):
        s = Student.objects.create(name="Richard Cypher",
                      average=3.14159)
        assert s
        student = Student.objects.get_by_id(s.id)
        assert student
        self.assertEqual(3.14159, student.average)

    def test_indexing(self):
        Student.objects.create(name="Richard Cypher", average=3.14159)
        Student.objects.create(name="Kahlan Amnell", average=92.45)
        Student.objects.create(name="Zeddicus Zorander", average=99.99)
        Student.objects.create(name="Cara", average=84.91)
        good = Student.objects.zfilter(average__gt=50.0)
        self.assertEqual(3, len(good))
        self.assertTrue("Richard Cypher",
                Student.objects.filter(average=3.14159)[0].name)



class Task(models.Model):
    name = models.Attribute()
    done = models.BooleanField()

class BooleanFieldTestCase(RediscoTestCase):
    def test_attribute(self):
        t = Task(name="Cook dinner", done=False)
        assert t.save()
        self.assertFalse(t.done)

    def test_saved_attribute(self):
        t = Task(name="Cook dinner", done=False)
        assert t.save()

        t = Task.objects.all()[0]
        self.assertFalse(t.done)
        t.done = True
        assert t.save()

        t = Task.objects.all()[0]
        self.assertTrue(t.done)

    def test_indexing(self):
        assert Task.objects.create(name="Study Lua", done=False)
        assert Task.objects.create(name="Read News", done=True)
        assert Task.objects.create(name="Buy Dinner", done=False)
        assert Task.objects.create(name="Visit Sick Friend", done=False)
        assert Task.objects.create(name="Play", done=True)
        assert Task.objects.create(name="Sing a song", done=False)
        assert Task.objects.create(name="Pass the Exam", done=True)
        assert Task.objects.create(name="Dance", done=False)
        assert Task.objects.create(name="Code", done=True)
        done = Task.objects.filter(done=True)
        unfin = Task.objects.filter(done=False)
        self.assertEqual(4, len(done))
        self.assertEqual(5, len(unfin))



class ListFieldTestCase(RediscoTestCase):
    def test_basic(self):
        class Cake(models.Model):
            name = models.Attribute()
            ingredients = models.ListField(str)
            sizes = models.ListField(int)

        Cake.objects.create(name="StrCake",
                            ingredients=['strawberry', 'sugar', 'dough'],
                            sizes=[1, 2, 5])
        Cake.objects.create(name="Normal Cake",
                            ingredients=['sugar', 'dough'],
                            sizes=[1, 3, 5])
        Cake.objects.create(name="No Sugar Cake",
                            ingredients=['dough'],
                            sizes=[])
        cake = Cake.objects.all()[0]
        self.assertEqual(['strawberry', 'sugar', 'dough'],
                cake.ingredients)
        with_sugar = Cake.objects.filter(ingredients='sugar')
        self.assertTrue(2, len(with_sugar))
        self.assertEqual([1, 2, 5], with_sugar[0].sizes)
        self.assertEqual([1, 3, 5], with_sugar[1].sizes)

        size1 = Cake.objects.filter(sizes=str(2))
        self.assertEqual(1, len(size1))

        cake.sizes = None
        cake.ingredients = None
        assert cake.save()

        cake = Cake.objects.get_by_id(cake.id)
        self.assertEqual([], cake.sizes)
        self.assertEqual([], cake.ingredients)

    def test_list_of_reference_fields(self):
        class Book(models.Model):
            title = models.Attribute(required=True)
            date_published = models.DateField(required=True)

        class Author(models.Model):
            name = models.Attribute(required=True)
            books = models.ListField(Book)

        book = Book.objects.create(
                title="University Physics With Modern Physics",
                date_published=date(2007, 4, 2))
        assert book

        author1 = Author.objects.create(name="Hugh Young",
                books=[book])
        author2 = Author.objects.create(name="Roger Freedman",
                books=[book])

        assert author1
        assert author2
        author1 = Author.objects.get_by_id(1)
        author2 = Author.objects.get_by_id(2)
        self.assertTrue(book in author1.books)
        self.assertTrue(book in author2.books)

        book = Book.objects.create(
                title="University Physics With Modern Physics Paperback",
                date_published=date(2007, 4, 2))

        author1.books.append(book)
        assert author1.save()

        author1 = Author.objects.get_by_id(1)
        self.assertEqual(2, len(author1.books))

    def test_lazy_reference_field(self):
        class User(models.Model):
            name = models.Attribute()
            likes = models.ListField('Link')

            def likes_link(self, link):
                if self.likes is None:
                    self.likes = [link]
                    self.save()
                else:
                    if link not in self.likes:
                        self.likes.append(link)
                        self.save()

        class Link(models.Model):
            url = models.Attribute()

        user = User.objects.create(name="Lion King")
        assert Link.objects.create(url="http://google.com")
        assert Link.objects.create(url="http://yahoo.com")
        assert Link.objects.create(url="http://github.com")
        assert Link.objects.create(url="http://bitbucket.org")

        links = Link.objects.all().limit(3)

        for link in links:
            user.likes_link(link)

        user = User.objects.get_by_id(1)
        self.assertEqual("http://google.com", user.likes[0].url)
        self.assertEqual("http://yahoo.com", user.likes[1].url)
        self.assertEqual("http://github.com", user.likes[2].url)
        self.assertEqual(3, len(user.likes))


class ReferenceFieldTestCase(RediscoTestCase):
    def test_basic(self):
        class Word(models.Model):
            placeholder = models.Attribute()

        class Character(models.Model):
            n = models.IntegerField()
            m = models.Attribute()
            word = models.ReferenceField(Word)

        Word.objects.create()
        word = Word.objects.all()[0]
        Character.objects.create(n=32, m='a', word=word)
        Character.objects.create(n=33, m='b', word=word)
        Character.objects.create(n=34, m='c', word=word)
        Character.objects.create(n=34, m='d')
        for char in Character.objects.all():
            self.assertEqual(word, char.word)
        a, b, c, d = list(Character.objects.all())
        self.assertTrue(a in word.character_set)
        self.assertTrue(b in word.character_set)
        self.assertTrue(c in word.character_set)
        self.assertTrue(d not in word.character_set)
        self.assertEqual(3, len(word.character_set))

    def test_lazy_reference_field(self):
        class User(models.Model):
            name = models.Attribute()
            address = models.ReferenceField('Address')

        class Address(models.Model):
            street_address = models.Attribute()
            city = models.Attribute()
            zipcode = models.Attribute()

        address = Address.objects.create(street_address="32/F Redisville",
                city="NoSQL City", zipcode="1.3.18")
        assert address
        user = User.objects.create(name="Richard Cypher", address=address)
        assert user

        u = User.objects.all()[0]
        self.assertEqual("32/F Redisville", u.address.street_address)
        self.assertEqual("NoSQL City", u.address.city)
        self.assertEqual("1.3.18", u.address.zipcode)


class DateTimeFieldTestCase(RediscoTestCase):

    def test_basic(self):
        from datetime import datetime
        n = datetime(2009, 12, 31)
        class Post(models.Model):
            title = models.Attribute()
            date_posted = models.DateTimeField()
            created_at = models.DateTimeField(auto_now_add=True)
        post = Post(title="First!", date_posted=n)
        assert post.save()
        post = Post.objects.get_by_id(post.id)
        self.assertEqual(n, post.date_posted)
        assert post.created_at


class CounterFieldTestCase(RediscoTestCase):

    def test_basic(self):
        class Post(models.Model):
            title = models.Attribute()
            body = models.Attribute(indexed=False)
            liked = models.Counter()

        post = Post.objects.create(title="First!",
                body="Lorem ipsum")
        self.assert_(post)
        post.incr('liked')
        post.incr('liked', 2)
        post = Post.objects.get_by_id(post.id)
        self.assertEqual(3, post.liked)
        post.decr('liked', 2)
        post = Post.objects.get_by_id(post.id)
        self.assertEqual(1, post.liked)


class MutexTestCase(RediscoTestCase):

    def setUp(self):
        super(MutexTestCase, self).setUp()
        self.p1 = Person.objects.create(first_name="Dick")
        self.p2 = Person.objects.get_by_id(self.p1.id)

    def test_instance_should_not_modify_locked(self):
        time1, time2 = {}, {}

        def f1(person, t):
            with Mutex(person):
                time.sleep(0.4)
                t['time'] = time.time()

        def f2(person, t):
            with Mutex(person):
                t['time'] = time.time()

        t1 = Thread(target=f1, args=(self.p1, time1,))
        t2 = Thread(target=f2, args=(self.p2, time2,))
        t1.start()
        time.sleep(0.1)
        t2.start()
        t1.join()
        t2.join()
        self.assert_(time2['time'] > time1['time'])

    def test_lock_expired(self):
        Mutex(self.p1).lock()
        with Mutex(self.p2):
            self.assert_(True)
