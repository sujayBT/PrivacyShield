const l = require('./node_modules/lucide-react');
const want = ['Instagram','Twitter','Linkedin','MessageSquare','Globe','Users','Search','Clock','Trash2','ChevronDown','ChevronUp','AlertTriangle','Shield','Activity','ExternalLink','RefreshCw','Eye'];
want.forEach(n => console.log(n, n in l ? 'OK' : 'MISSING'));
