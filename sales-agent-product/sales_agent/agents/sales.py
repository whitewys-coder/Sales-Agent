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
        result = self.provider.extract('Write a professional international B2B first-contact email in English AND a complete matching Chinese version based ONLY on the verified account below. '
            'One verified product/process fact, one complementary task, one concrete question, normally 100–160 words. Recent news or purchasing intent is optional; never invent Why Now. '
            'Return subject/body in English and subject_zh/body_zh in Chinese. Facts, scope, promises and call to action must agree. '
            'No invented gains, certifications, attachment claims, or whole-model <1MB claims. No signature (app adds it).\n' +
            json.dumps(account, ensure_ascii=False), obj({'subject': TEXT, 'body': TEXT,'subject_zh':TEXT,'body_zh':TEXT}))
        if any(not result.get(k,'').strip() for k in ('subject','body','subject_zh','body_zh')):
            raise ValueError('Complete English and Chinese subject/body required')
        return {'id': uid(), 'account_id': account['id'], 'to': account['email'],
                'subject_zh':result['subject_zh'], 'body_zh':result['body_zh']+'\n\nAlen Wang\nXeroptix\nAlenWang@xeroptix.com\nhttps://xeroptix.com',
                'subject': result['subject'], 'body': result['body'] + '\n\nBest regards,\n' +
                'Alen Wang\nXeroptix\nAlenWang@xeroptix.com\nhttps://xeroptix.com',
                'status': 'pending', 'created_at': now(), 'approved_hash': '', 'demo': False}
