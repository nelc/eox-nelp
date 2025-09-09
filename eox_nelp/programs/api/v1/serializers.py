"""Programs API v1 Serializers."""
from rest_framework import serializers


class ProgramsMetadataSerializer(serializers.Serializer):
    """
    Serializer for programs metadata.

    This serializer handles the metadata for a specific course program.
    """
    trainer_type = serializers.IntegerField(default=10, read_only=True)
    Type_of_Activity = serializers.IntegerField()
    Mandatory = serializers.CharField(max_length=2)
    Program_ABROVE = serializers.CharField(max_length=2)
    Program_code = serializers.CharField(max_length=64)

    def validate_Mandatory(self, value):
        """Validate Mandatory field."""
        valid_values = ["01", "00"]
        if value not in valid_values:
            raise serializers.ValidationError(
                f"Mandatory must be one of: {', '.join(valid_values)}"
            )
        return value

    def validate_Program_ABROVE(self, value):
        """Validate Program_ABROVE field."""
        valid_values = ["01", "00"]
        if value not in valid_values:
            raise serializers.ValidationError(
                f"Program_ABROVE must be one of: {', '.join(valid_values)}"
            )
        return value

    def validate_Program_code(self, value):
        """Validate Program_code field."""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Program_code cannot be empty")
        return value.strip()
