"""Тесты"""
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from main.models import Category,Quiz,Question,Answer, QuizResult,Achievement,UserAchievement,GameSession,GameParticipant,GameAnswer
"""
Вася: GameAnswer
"""

class CategoryTest(TestCase):
    fixtures = ['db.json']
    def setUp(self):
        self.client = Client()
        self.response = self.client.get('') #?
        #print(self.response.context)
    def test_categoty_response(self):
        self.assertEqual(self.response.status_code, 200)
        #self.assertContains(self.response,)
   # def test_category_context(self):
        #self.assertEqual(self.response.context[''], )
        #self.assertEqual(self.response.context[''], )
        #self.assertEqual(self.response.context[''], )



class Quiz(TestCase):
    fixtures = ["db.json"]

    def setUp(self):
        self.client = Client()
        self.user = User.objects.get(username='zxcdeadinside')
        self.client.force_login(self.user)
        self.response = self.client.get('/quizzises/')
        #print(self.response.context)
    def test_quiz_response(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(self.response.context["user"], self.user)
        self.assertEqual(str(self.response.context["request"]), "<WSGIRequest: GET '/quizzises/'>")

        #self.assertIn('form', self.response.context)  ?




''''
class CalcPage(TestCase):
    fixtures = [
        "test_database.json"
    ]
    def setUp(self):
        self.client = Client()
        self.user = User.objects.get(username='vasya')
        self.client.force_login(self.user)

        self.response = self.client.get('/calc/')

    def test_calc_response(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(self.response.context["pagename"], "Калькулятор")
        self.assertIn('form', self.response.context)

    def test_simple_calc_success(self): #проверка суммы
        self.response = self.client.post("/calc/", {'first': 1, 'second':2})
        self.assertEqual(self.response.status_code, 200)
        self.assertEqual(self.response.context["first_value"],'1')
        self.assertEqual(self.response.context["second_value"],'2')
        self.assertEqual(self.response.context["result"],3)

    def test_invalid_post(self):
        self.response = self.client.post('/calc/', {'first': "ahaha", 'second':"ohoho"})
        self.assertEqual(self.response.status_code, 200)
        self.assertIn('form', self.response.context)
        self.assertGreater(len(self.response.context["form"].errors), 0)
        self.assertFormError(self.response.context["form"], "first", "Enter a whole number.")

    def test_history_add(self):
        record = CalcHistory(first=10,second=20, result=30,author=self.user,
                             date=datetime.datetime.now())
        record.save()
        self.response = self.client.get('/calc/')
        history = self.response.context["history"]
        last_record = history.last()
        self.assertEqual(last_record.first,10)
        self.assertEqual(last_record.second,20)
        self.assertEqual(last_record.result,30)
        '''