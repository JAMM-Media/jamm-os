TASK: Fix new client disappearing — refetch after creation

FILE: frontend/src/app/clients/page.tsx

After creating a client the page only adds it to localClients 
(in-memory). When the user navigates away and back, that state 
resets. Fix by triggering a refetch after creation so the new 
client is in the server-fetched list.

CHANGE 1 — Destructure refetch from useFetch.

Find:
  const { data, isLoading, error } = useFetch(() => clientsApi.list(), [])

Replace with:
  const { data, isLoading, error, refetch } = useFetch(() => clientsApi.list(), [])

CHANGE 2 — Call refetch after adding the client locally.

Find:
  function handleAddClient(client: Client) {
    setLocalClients((prev) => [client, ...prev])
  }

Replace with:
  function handleAddClient(client: Client) {
    setLocalClients((prev) => [client, ...prev])
    setTimeout(() => refetch(), 500)
  }

No other files need to be changed.