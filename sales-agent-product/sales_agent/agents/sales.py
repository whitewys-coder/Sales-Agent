import json
from ..provider import obj, TEXT
from ..store import now, uid


class SalesAgent:
    name = 'Sales Agent'

    def __init__(self, provider, config):
        self.provider, self.config = provider, config

    def run(self, account):
        if not account.get('validated') or account['status'] != 'pending_review':
            return None
        result = self.provider.extract('Write a concise English first-contact email based ONLY on the verified account below. '
            'One verified product/process fact, one complementary task, one concrete question, normally 100–160 words. Recent news or purchasing intent is optional; never invent Why Now. '
            'No invented gains, certifications, attachment claims, or whole-model <1MB claims. No signature (app adds it).\n' +
            json.dumps(account, ensure_ascii=False), obj({'subject': TEXT, 'body': TEXT}))
        return {'id': uid(), 'account_id': account['id'], 'to': account['email'],
                'subject': result['subject'], 'body': result['body'] + '\n\nBest regards,\n' +
                'Alen Wang\nXeroptix\nAlenWang@xeroptix.com\nhttps://xeroptix.com',
                'status': 'pending', 'created_at': now(), 'approved_hash': '', 'demo': False}
