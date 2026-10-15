from datetime import date
from zoneinfo import ZoneInfo
from datetime import datetime
from ..rules import CAPS, SUBCAPS, research_eligible, email_eligible

class ScoringAgent:
    name='Scoring Agent'
    def run(self,a,today=None):
        today=today or datetime.now(ZoneInfo('Asia/Shanghai')).date()
        urls={s.get('url') for s in a.get('sources',[])}
        points={k:0 for k in CAPS}
        for key in ('trigger','technical_fit','decision_maker','public_email','strategic'):
            parts=a.get('score_evidence',{}).get(key,[])
            caps=SUBCAPS.get(key,[25])
            if len(parts)!=len(caps):continue
            for part,cap in zip(parts,caps):
                v=part.get('points',0)
                if type(v) is int and 0<=v<=cap and part.get('reason') and part.get('urls') and set(part['urls'])<=urls:
                    points[key]+=v
        try:age=(today-date.fromisoformat(a.get('trigger_date',''))).days
        except (TypeError,ValueError):age=999
        if a.get('recent_trigger_verified'):
            points['freshness']=15 if 0<=age<=30 else 10 if age<=60 and age>=0 else 5 if age<=90 and age>=0 else 0
        else:points['trigger']=0
        n=a.get('employees',0)
        if type(n) is int and a.get('employees_verified'):points['size']=5 if 10<=n<=500 else 3 if 501<=n<=2000 else 1 if n>0 else 0
        if not a.get('contact_verified'):points['decision_maker']=0
        if not email_eligible(a):points['public_email']=0
        if not a.get('technical_fit'):points['technical_fit']=0
        elif not any(s.get('kind') in ('scene','product') for s in a.get('sources',[])):points['technical_fit']=min(15,points['technical_fit'])
        a['score_breakdown'],a['score']=points,sum(points.values())
        a['rule_version']='3.3'
        a['validated']=research_eligible(a) and bool(a.get('contact_verified')) and email_eligible(a)
        a['channel']='priority' if a['validated'] and a['score']>=85 and a.get('recent_trigger_verified') else 'exploratory'
        a['status']='pending_review' if a['validated'] else 'needs_contact' if research_eligible(a) else 'watch'
        return a
