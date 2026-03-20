from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Alert, Company, DataPoint, WatchList
from .serializers import AlertSerializer, CompanySerializer, DataPointSerializer, WatchListSerializer


class CompanyListCreateView(generics.ListCreateAPIView):
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Company.objects.all()
        sector = self.request.query_params.get("sector")
        country = self.request.query_params.get("country")
        search = self.request.query_params.get("search")
        if sector:
            qs = qs.filter(sector__icontains=sector)
        if country:
            qs = qs.filter(country__icontains=country)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class CompanyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Company.objects.all()


class CompanyDataPointListView(generics.ListAPIView):
    """GET /api/companies/{pk}/data-points/ — list data points for a company."""
    serializer_class = DataPointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataPoint.objects.filter(
            company_id=self.kwargs["pk"]
        ).order_by("-extracted_at")


class WatchListView(generics.ListCreateAPIView):
    """GET/POST /api/companies/{pk}/watchlist/ — manage watchlist for current user."""
    serializer_class = WatchListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WatchList.objects.filter(
            user_id=self.request.user.id,
            company_id=self.kwargs["pk"],
        )

    def perform_create(self, serializer):
        serializer.save(
            user_id=self.request.user.id,
            company_id=self.kwargs["pk"],
        )


class AlertListCreateView(generics.ListCreateAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Alert.objects.filter(user_id=self.request.user.id)

    def perform_create(self, serializer):
        import uuid
        serializer.save(user_id=self.request.user.id, id=uuid.uuid4())
