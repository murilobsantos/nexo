import * as React from 'react';
import { createRoot } from 'react-dom/client';

const result: { status: string } = { status: 'Stack compilada; produto ainda não implementado.' };
createRoot(document.getElementById('root')!).render(React.createElement('p', null, result.status));
